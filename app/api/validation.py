# app/api/validation.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Chain, User
from app.api.schemas import ChainValidationEntry, InvalidMessageInfo
from app.api.deps import get_current_user, get_message_repo
from app.repositories.message_repository import MessageRepository

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/chains/{chain_id}", response_model=List[ChainValidationEntry])
async def validate_chain(
    chain_id: int,
    repo: MessageRepository = Depends(get_message_repo),
    current_user: User = Depends(get_current_user),
):
    """Validate a chain's integrity."""
    # Check chain exists and access
    result = await repo.session.execute(
        select(Chain).where(Chain.id == chain_id)
    )
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(
            status_code=404,
            detail="Chain not found",
        )
    
    # Check access for private chains
    if chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied to private chain",
            )
    
    validation = await repo.validate_chain(chain_id)
    
    return [
        ChainValidationEntry(
            block_height=block_height,
            hash=hash_val,
            prev_hash=prev_hash,
            links_valid=links_valid,
            content_valid=content_valid,
        )
        for block_height, hash_val, prev_hash, links_valid, content_valid in validation
    ]


@router.get("/chains/{chain_id}/invalid", response_model=List[InvalidMessageInfo])
async def get_invalid_messages(
    chain_id: int,
    repo: MessageRepository = Depends(get_message_repo),
    current_user: User = Depends(get_current_user),
):
    """Get all invalid messages in a chain."""
    # Check chain exists and access
    result = await repo.session.execute(
        select(Chain).where(Chain.id == chain_id)
    )
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(
            status_code=404,
            detail="Chain not found",
        )
    
    if chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )
    
    return await repo.get_invalid_messages(chain_id)


@router.get("/chains/{chain_id}/valid", response_model=bool)
async def is_chain_valid(
    chain_id: int,
    repo: MessageRepository = Depends(get_message_repo),
    current_user: User = Depends(get_current_user),
):
    """Quick check if chain is valid."""
    # Check chain exists and access
    result = await repo.session.execute(
        select(Chain).where(Chain.id == chain_id)
    )
    chain = result.scalar_one_or_none()
    
    if not chain:
        raise HTTPException(
            status_code=404,
            detail="Chain not found",
        )
    
    if chain.chain_type == "private":
        if current_user.id not in (chain.participant1_id, chain.participant2_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )
    
    return await repo.is_chain_valid(chain_id)
