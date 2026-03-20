from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, 
    DateTime, ForeignKey, Index, PrimaryKeyConstraint,
    ForeignKeyConstraint, text, func, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    pubkey = Column(String, unique=True, nullable=False, index=True)
    username = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True))

    # Relationships
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    contacts = relationship("Contact", foreign_keys="Contact.user_id", back_populates="user")
    chains_as_participant1 = relationship("Chain", foreign_keys="Chain.participant1_id")
    chains_as_participant2 = relationship("Chain", foreign_keys="Chain.participant2_id")

    __table_args__ = (
        Index('idx_users_username_gin', text("to_tsvector('simple', COALESCE(username, ''))"), postgresql_using='gin'),
    )


class Chain(Base):
    __tablename__ = "chains"

    id = Column(BigInteger, primary_key=True)
    chain_type = Column(String, nullable=False)
    participant1_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    participant2_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    chain_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    messages = relationship("Message", back_populates="chain", order_by="Message.block_height")

    __table_args__ = (
        Index('idx_chains_participants', 'participant1_id', 'participant2_id'),
        Index('idx_chains_type', 'chain_type'),
    )

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)  # Добавьте autoincrement=True
    hash = Column(String, nullable=False)
    prev_hash = Column(String)
    signature = Column(String, nullable=False)
    chain_id = Column(BigInteger, ForeignKey('chains.id', ondelete='CASCADE'), nullable=False)
    sender_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = Column(Text, nullable=False)
    content_iv = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=text('now()'), nullable=False, primary_key=True)
    block_height = Column(BigInteger)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))


    # Relationships
    chain = relationship("Chain", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")
    attachments = relationship("Attachment", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        # Составной primary key включает created_at
        PrimaryKeyConstraint('id', 'created_at', name='pk_messages'),
        
        # УНИКАЛЬНОСТЬ: теперь hash уникален в рамках партиции
        # Для глобальной уникальности используем составной unique constraint
        UniqueConstraint('hash', 'created_at', name='uq_messages_hash_created'),
        
        # Индексы
        Index('idx_messages_hash', 'hash'),
        Index('idx_messages_chain_created', 'chain_id', 'created_at'),
        Index('idx_messages_sender_created', 'sender_id', 'created_at'),
        Index('idx_messages_chain_block', 'chain_id', 'block_height'),
        Index('idx_messages_search', text("to_tsvector('russian', COALESCE(content, ''))"), postgresql_using='gin'),
        
        # Партиционирование
        {
            'postgresql_partition_by': 'RANGE (created_at)',
        }
    )

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(BigInteger, primary_key=True)
    message_id = Column(BigInteger, nullable=False)
    message_created_at = Column(DateTime(timezone=True), nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_hash = Column(String)
    file_size = Column(BigInteger)
    mime_type = Column(String)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    message = relationship("Message", back_populates="attachments")

    __table_args__ = (
        # Составной внешний ключ к messages
        ForeignKeyConstraint(
            ['message_id', 'message_created_at'],
            ['messages.id', 'messages.created_at'],
            ondelete="CASCADE",
            name='fk_attachments_message'
        ),
        Index('idx_attachments_message', 'message_id'),
        Index('idx_attachments_hash', 'file_hash'),
    )


class Contact(Base):
    __tablename__ = "contacts"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    contact_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="contacts")
    contact = relationship("User", foreign_keys=[contact_id])
