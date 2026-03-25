# app/api/messages.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import os
import shutil
import hashlib
from datetime import datetime, timezone
from app.api.websocket import manager
from app.database import get_db
from app.models import User, Chain, Message, Attachment
from app.api.schemas import (
    MessageCreate, MessageResponse, MessageWithAttachments,
    ChainValidationEntry, InvalidMessageInfo
)
from app.api.deps import get_current_user, get_message_repo
from app.repositories.message_repository import MessageRepository

from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/messages", tags=["messages"])

@router.get("/chains/{chain_id}", response_model=List[MessageResponse])
async def get_chain_messages(
    chain_id: int,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get messages from a chain."""
    # Check chain exists and access
    result = await db.execute(select(Chain).where(Chain.id == chain_id))
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )
    
    # Check access for private chains
    if chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to private chain",
            )
    
    # Eager load the sender relationship
    result = await db.execute(
        select(Message)
        .options(selectinload(Message.sender))  # This loads the sender
        .where(
            Message.chain_id == chain_id,
            Message.is_deleted == False,
        )
        .order_by(Message.block_height)
        .limit(limit)
        .offset(offset)
    )
    
    messages = result.scalars().all()
    
    # Convert to response models (sender will be included)
    return messages

@router.get("/chains/{chain_id}/messages/{message_id}", response_model=MessageWithAttachments)
async def get_message(
    chain_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific message with attachments."""
    # Check chain access
    result = await db.execute(select(Chain).where(Chain.id == chain_id))
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )
    
    if chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
    
    # Eager load sender and attachments
    result = await db.execute(
        select(Message)
        .options(
            selectinload(Message.sender),
            selectinload(Message.attachments)
        )
        .where(
            Message.chain_id == chain_id,
            Message.id == message_id,
            Message.is_deleted == False,
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    return MessageWithAttachments(
        **message.__dict__,
        attachments=message.attachments,
    )

@router.post("/chains/{chain_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    chain_id: int,
    message_data: MessageCreate,
    repo: MessageRepository = Depends(get_message_repo),
    current_user: User = Depends(get_current_user),
):
    """Create a new message in a chain."""
    # Get chain to check type and access
    result = await repo.session.execute(
        select(Chain).where(Chain.id == chain_id)
    )
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )
    
    # Check access for private chains
    if chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot post to private chain",
            )
    
    # Check if chain has any messages
    result = await repo.session.execute(
        select(func.count(Message.id))
        .where(Message.chain_id == chain_id)
    )
    count = result.scalar()
    
    if count == 0:
        # Genesis message
        if message_data.prev_hash is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Genesis message cannot have prev_hash",
            )
        
        message = await repo.create_genesis_message(
            chain_id=chain_id,
            sender_id=current_user.id,
            content=message_data.content,
            signature=message_data.signature,
        )
    else:
        # Regular message
        if not message_data.prev_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="prev_hash required for non-genesis message",
            )
        
        message = await repo.add_message_to_chain(
            chain_id=chain_id,
            sender_id=current_user.id,
            content=message_data.content,
            signature=message_data.signature,
            prev_hash=message_data.prev_hash,
        )
    
    await repo.session.commit()
    await repo.session.refresh(message)  # FIXED: Use repo.session instead of db

    # Broadcast to WebSocket connections
    await manager.send_to_chain(chain_id, {
        "type": "new_message",
        "chain_id": chain_id,
        "message": {
            "id": message.id,
            "hash": message.hash,
            "content": message.content,
            "sender_id": message.sender_id,
            "sender": {
                "id": current_user.id,
                "username": current_user.username,
                "pubkey": current_user.pubkey
            } if current_user else None,
            "created_at": message.created_at.isoformat(),
            "block_height": message.block_height,
            "signature": message.signature,
            "prev_hash": message.prev_hash
        }
    })

    return message

@router.post("/chains/{chain_id}/with-attachments", response_model=MessageResponse)
async def create_message_with_attachments(
    chain_id: int,
    content: str = Form(...),
    signature: str = Form(...),
    prev_hash: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),  # db is defined here
    current_user: User = Depends(get_current_user),
):
    """Create a message with file attachments."""
    repo = MessageRepository(db)
    
    # Check chain access
    result = await db.execute(select(Chain).where(Chain.id == chain_id))
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chain not found",
        )
    
    if chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot post to private chain",
            )
    
    # Check if chain has any messages
    result = await db.execute(
        select(func.count(Message.id))
        .where(Message.chain_id == chain_id)
    )
    count = result.scalar()
    
    # Create message
    if count == 0:
        if prev_hash is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Genesis message cannot have prev_hash",
            )
        
        message = await repo.create_genesis_message(
            chain_id=chain_id,
            sender_id=current_user.id,
            content=content,
            signature=signature,
        )
    else:
        if not prev_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="prev_hash required for non-genesis message",
            )
        
        message = await repo.add_message_to_chain(
            chain_id=chain_id,
            sender_id=current_user.id,
            content=content,
            signature=signature,
            prev_hash=prev_hash,
        )
    
    # Save attachments
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    for file in files:
        # Generate unique filename
        file_hash = hashlib.sha256(await file.read()).hexdigest()
        await file.seek(0)
        
        ext = os.path.splitext(file.filename)[1]
        filename = f"{file_hash}{ext}"
        filepath = os.path.join(upload_dir, filename)
        
        # Save file
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Create attachment record
        attachment = Attachment(
            message_id=message.id,
            message_created_at=message.created_at,
            file_name=file.filename,
            file_path=filepath,
            file_hash=file_hash,
            file_size=os.path.getsize(filepath),
            mime_type=file.content_type,
        )
        db.add(attachment)
    
    await db.commit()
    await db.refresh(message)

    # Broadcast to WebSocket connections
    await manager.send_to_chain(chain_id, {
        "type": "new_message",
        "chain_id": chain_id,
        "message": {
            "id": message.id,
            "hash": message.hash,
            "content": message.content,
            "sender_id": message.sender_id,
            "sender": {
                "id": current_user.id,
                "username": current_user.username,
                "pubkey": current_user.pubkey
            } if current_user else None,
            "created_at": message.created_at.isoformat(),
            "block_height": message.block_height,
            "signature": message.signature,
            "prev_hash": message.prev_hash
        }
    })
    
    return message


@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete a message."""
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    # Check if user is the sender
    if message.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete your own messages",
        )
    
    message.is_deleted = True
    message.deleted_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"status": "deleted"}
