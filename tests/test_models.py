# tests/test_models.py

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload  # Добавьте этот импорт
from datetime import datetime, timedelta
from app.models import User, Chain, Message, Attachment, Contact
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Тест создания пользователя"""
    user = User(
        pubkey="test_key_456",
        username="testuser",
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    
    # Проверяем, что пользователь создан
    result = await db_session.execute(
        select(User).where(User.pubkey == "test_key_456")
    )
    saved_user = result.scalar_one()
    assert saved_user.username == "testuser"
    assert saved_user.id is not None

@pytest.mark.asyncio
async def test_create_chain(db_session: AsyncSession, test_user: User):
    """Тест создания цепочки"""
    chain = Chain(
        chain_type="private",
        participant1_id=test_user.id,
        participant2_id=test_user.id,  # для теста сам с собой
        created_at=datetime.utcnow()
    )
    db_session.add(chain)
    await db_session.commit()
    
    result = await db_session.execute(
        select(Chain).where(Chain.id == chain.id)
    )
    saved_chain = result.scalar_one()
    assert saved_chain.chain_type == "private"
    assert saved_chain.participant1_id == test_user.id

@pytest.mark.asyncio
async def test_create_message(db_session: AsyncSession, test_user: User, test_chain: Chain):
    """Тест создания сообщения"""
    message = Message(
        hash="test_hash_123",
        prev_hash=None,
        signature="test_sig_456",
        chain_id=test_chain.id,
        sender_id=test_user.id,
        content="Hello, World!",
        block_height=1,
        created_at=datetime.utcnow()
    )
    db_session.add(message)
    await db_session.commit()
    
    result = await db_session.execute(
        select(Message).where(Message.hash == "test_hash_123")
    )
    saved_msg = result.scalar_one()
    assert saved_msg.content == "Hello, World!"
    assert saved_msg.block_height == 1

@pytest.mark.asyncio
async def test_message_with_attachment(db_session: AsyncSession, test_user: User, test_chain: Chain):
    """Тест сообщения с вложением"""
    # Создаем сообщение
    message = Message(
        hash="test_hash_attach",
        signature="test_sig",
        chain_id=test_chain.id,
        sender_id=test_user.id,
        content="Check this file!",
        block_height=1,
        created_at=datetime.utcnow()
    )
    db_session.add(message)
    await db_session.flush()
    
    # Создаем вложение
    attachment = Attachment(
        message_id=message.id,
        message_created_at=message.created_at,
        file_name="test.txt",
        file_path="/uploads/test.txt",
        file_hash="file_hash_123",
        file_size=1024,
        mime_type="text/plain"
    )
    db_session.add(attachment)
    await db_session.commit()
    
    # Проверяем связь - ВАЖНО: загружаем attachments явно
    result = await db_session.execute(
        select(Message)
        .where(Message.id == message.id)
        .options(selectinload(Message.attachments))  # Явная загрузка attachments
    )
    msg_with_attach = result.scalar_one()
    
    # Теперь можно безопасно обращаться к attachments
    assert len(msg_with_attach.attachments) == 1
    assert msg_with_attach.attachments[0].file_name == "test.txt"
