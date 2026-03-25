# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging
from typing import Dict, Set

from app.database import AsyncSessionLocal
from app.models import User, Chain

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Store active connections: {chain_id: {websocket: user_id}}
        self.active_connections: Dict[int, Dict[WebSocket, int]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int, chain_id: int):
        await websocket.accept()
        
        if chain_id not in self.active_connections:
            self.active_connections[chain_id] = {}
        
        self.active_connections[chain_id][websocket] = user_id
        
        logger.info(f"User {user_id} connected to chain {chain_id}. Total connections: {len(self.active_connections[chain_id])}")
    
    def disconnect(self, websocket: WebSocket, chain_id: int):
        if chain_id in self.active_connections:
            if websocket in self.active_connections[chain_id]:
                user_id = self.active_connections[chain_id][websocket]
                del self.active_connections[chain_id][websocket]
                logger.info(f"User {user_id} disconnected from chain {chain_id}")
            
            if not self.active_connections[chain_id]:
                del self.active_connections[chain_id]
    
    async def send_to_chain(self, chain_id: int, message_data: dict):
        """Send message to all users connected to this chain"""
        if chain_id not in self.active_connections:
            logger.debug(f"No active connections for chain {chain_id}")
            return
        
        sent_count = 0
        disconnected = []
        
        for websocket, user_id in self.active_connections[chain_id].items():
            try:
                await websocket.send_json(message_data)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to user {user_id} on chain {chain_id}: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            self.disconnect(websocket, chain_id)
        
        if sent_count > 0:
            logger.debug(f"Sent message to {sent_count} connections on chain {chain_id}")

manager = ConnectionManager()

@router.websocket("/ws/{chain_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chain_id: int,
):
    """WebSocket endpoint for real-time messages in a chain."""
    # Create a database session manually for WebSocket
    async with AsyncSessionLocal() as db:
        # Authenticate user from query parameter
        pubkey = websocket.query_params.get("pubkey")
        
        if not pubkey:
            await websocket.close(code=1008, reason="Missing pubkey")
            return
        
        # Get user
        result = await db.execute(
            select(User).where(User.pubkey == pubkey)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
        
        # Check chain access
        result = await db.execute(select(Chain).where(Chain.id == chain_id))
        chain = result.scalar_one_or_none()
        
        if not chain:
            await websocket.close(code=1008, reason="Chain not found")
            return
        
        # Verify private chain access
        if chain.chain_type == "private":
            if user.id not in (chain.participant1_id, chain.participant2_id):
                await websocket.close(code=1003, reason="Access denied")
                return
        
        # Connect to chain
        await manager.connect(websocket, user.id, chain_id)
        
        try:
            # Send initial connection confirmation
            await websocket.send_json({
                "type": "connected",
                "chain_id": chain_id,
                "user_id": user.id,
                "message": f"Connected to chain {chain_id}"
            })
            
            # Keep connection alive and handle incoming messages
            while True:
                # Receive and handle messages (could be ping/pong or new messages)
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif message.get("type") == "message_read":
                        # Optional: track read receipts
                        pass
                        
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {data}")
                    
        except WebSocketDisconnect:
            manager.disconnect(websocket, chain_id)
        except Exception as e:
            logger.error(f"WebSocket error for user {user.id}: {e}")
            manager.disconnect(websocket, chain_id)
