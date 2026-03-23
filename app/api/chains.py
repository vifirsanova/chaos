# app/api/chains.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models import User, Chain, Message
from app.api.schemas import ChainCreate, ChainResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/chains", tags=["chains"])


@router.post("/", response_model=ChainResponse, status_code=status.HTTP_201_CREATED)
async def create_chain(
    chain_data: ChainCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chain."""
    chain = Chain(
        chain_type=chain_data.chain_type,
        chain_name=chain_data.chain_name,
    )
    
    # Handle private chains
    if chain_data.chain_type == "private":
        if not chain_data.participant1_id or not chain_data.participant2_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Private chains require both participants",
            )
        
        # Ensure participant1_id < participant2_id
        p1, p2 = sorted([chain_data.participant1_id, chain_data.participant2_id])
        chain.participant1_id = p1
        chain.participant2_id = p2
        
        # Check if dialog already exists
        result = await db.execute(
            select(Chain).where(
                and_(
                    Chain.chain_type == "private",
                    Chain.participant1_id == p1,
                    Chain.participant2_id == p2,
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Private chain already exists",
            )
    
    db.add(chain)
    await db.commit()
    await db.refresh(chain)
    
    return chain


@router.get("/", response_model=List[ChainResponse])
async def get_chains(
    chain_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chains for current user."""
    query = select(Chain)
    
    if chain_type:
        query = query.where(Chain.chain_type == chain_type)
    
    # For private chains, only show chains where user is participant
    query = query.where(
        (Chain.chain_type != "private") |
        ((Chain.participant1_id == current_user.id) | 
         (Chain.participant2_id == current_user.id))
    )
    
    query = query.order_by(Chain.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{chain_id}", response_model=ChainResponse)
async def get_chain(
    chain_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chain by ID."""
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
    
    return chain
