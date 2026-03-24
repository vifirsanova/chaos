# app/api/schemas.py
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# User schemas
class UserBase(BaseModel):
    pubkey: str
    username: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    username: Optional[str] = None


# Chain schemas
class ChainBase(BaseModel):
    chain_type: str = Field(..., pattern="^(global|private|feed|myvoid)$")
    chain_name: Optional[str] = None


class ChainCreate(ChainBase):
    participant1_id: Optional[int] = None
    participant2_id: Optional[int] = None


class ChainResponse(ChainBase):
    id: int
    participant1_id: Optional[int] = None
    participant2_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Message schemas
class MessageBase(BaseModel):
    content: str
    signature: str


class MessageCreate(MessageBase):
    prev_hash: Optional[str] = None

class MessageResponse(MessageBase):
    id: int
    hash: str
    prev_hash: Optional[str] = None
    chain_id: int
    sender_id: int
    sender: Optional[UserResponse] = None  # Add this field
    created_at: datetime
    block_height: int
    is_deleted: bool

    class Config:
        from_attributes = True

class MessageWithAttachments(MessageResponse):
    attachments: List["AttachmentResponse"] = []


# Attachment schemas
class AttachmentBase(BaseModel):
    file_name: str
    file_path: str
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class AttachmentCreate(AttachmentBase):
    pass


class AttachmentResponse(AttachmentBase):
    id: int
    message_id: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


# Contact schemas
class ContactCreate(BaseModel):
    contact_pubkey: str


class ContactResponse(BaseModel):
    user_id: int
    contact_id: int
    contact: UserResponse
    added_at: datetime

    class Config:
        from_attributes = True


# Chain validation schemas
class ChainValidationEntry(BaseModel):
    block_height: int
    hash: str
    prev_hash: Optional[str]
    links_valid: bool
    content_valid: bool


class InvalidMessageInfo(BaseModel):
    block_height: int
    hash: str
    prev_hash: Optional[str]
    errors: List[str]


# Update forward references
MessageWithAttachments.model_rebuild()
