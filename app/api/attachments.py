# app/api/attachments.py
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Attachment, Message, Chain, User
from app.api.deps import get_current_user

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}")
async def download_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a file attachment."""
    # Get attachment
    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    
    # Get message and check access
    result = await db.execute(
        select(Message).where(Message.id == attachment.message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    
    # Get chain and check access
    result = await db.execute(
        select(Chain).where(Chain.id == message.chain_id)
    )
    chain = result.scalar_one_or_none()
    
    if chain and chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
    
    # Check if file exists
    if not os.path.exists(attachment.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on server",
        )
    
    return FileResponse(
        attachment.file_path,
        filename=attachment.file_name,
        media_type=attachment.mime_type or "application/octet-stream",
    )
