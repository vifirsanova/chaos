# app/api/deps.py
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.repositories.message_repository import MessageRepository

api_key_header = APIKeyHeader(name="X-User-Pubkey", auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    pubkey: Optional[str] = Depends(api_key_header),
) -> User:
    """Get current user from pubkey header."""
    if not pubkey:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Pubkey header",
        )
    
    result = await db.execute(
        select(User).where(User.pubkey == pubkey)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with pubkey {pubkey} not found",
        )
    
    return user

async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    pubkey: Optional[str] = Depends(api_key_header),
) -> Optional[User]:
    """Get current user from pubkey header, returns None if not found."""
    if not pubkey:
        return None
    
    result = await db.execute(
        select(User).where(User.pubkey == pubkey)
    )
    user = result.scalar_one_or_none()
    
    return user

async def get_message_repo(
    db: AsyncSession = Depends(get_db),
) -> MessageRepository:
    """Get message repository instance."""
    return MessageRepository(db)


async def get_current_user_websocket(
    pubkey: str,
    db: AsyncSession,  # Remove Depends, pass db explicitly
) -> User:
    """Get current user from pubkey for WebSocket connections."""
    result = await db.execute(
        select(User).where(User.pubkey == pubkey)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with pubkey {pubkey} not found",
        )

    return user
