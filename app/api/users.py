# app/api/users.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone

from app.database import get_db
from app.models import User, Contact
from app.api.schemas import (
    UserCreate, UserResponse, UserUpdate, ContactCreate, ContactResponse
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user."""
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.pubkey == user_data.pubkey)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this pubkey already exists",
        )
    
    user = User(
        pubkey=user_data.pubkey,
        username=user_data.username,
        last_seen=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current user info."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user info."""
    if user_data.username is not None:
        current_user.username = user_data.username
    
    current_user.last_seen = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.get("/search", response_model=List[UserResponse])
async def search_users(
    q: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search users by username or pubkey."""
    # Simple search using ILIKE
    result = await db.execute(
        select(User)
        .where(
            (User.username.ilike(f"%{q}%")) |
            (User.pubkey.ilike(f"%{q}%"))
        )
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return user


# Contacts endpoints
@router.get("/me/contacts", response_model=List[ContactResponse])
async def get_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all contacts for current user."""
    result = await db.execute(
        select(Contact)
        .where(Contact.user_id == current_user.id)
    )
    contacts = result.scalars().all()
    
    # Load contact details
    response = []
    for contact in contacts:
        user_result = await db.execute(
            select(User).where(User.id == contact.contact_id)
        )
        contact_user = user_result.scalar_one()
        response.append(ContactResponse(
            user_id=contact.user_id,
            contact_id=contact.contact_id,
            contact=contact_user,
            added_at=contact.added_at,
        ))
    
    return response


@router.post("/me/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def add_contact(
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a contact by pubkey."""
    # Find the contact user
    result = await db.execute(
        select(User).where(User.pubkey == contact_data.contact_pubkey)
    )
    contact_user = result.scalar_one_or_none()
    
    if not contact_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this pubkey not found",
        )
    
    if contact_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add yourself as contact",
        )
    
    # Check if already a contact
    result = await db.execute(
        select(Contact).where(
            Contact.user_id == current_user.id,
            Contact.contact_id == contact_user.id,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already in contacts",
        )
    
    contact = Contact(
        user_id=current_user.id,
        contact_id=contact_user.id,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    
    return ContactResponse(
        user_id=contact.user_id,
        contact_id=contact.contact_id,
        contact=contact_user,
        added_at=contact.added_at,
    )


@router.delete("/me/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a contact."""
    result = await db.execute(
        select(Contact).where(
            Contact.user_id == current_user.id,
            Contact.contact_id == contact_id,
        )
    )
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    
    await db.delete(contact)
    await db.commit()
