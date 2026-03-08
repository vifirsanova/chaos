# tests/test_repository.py

import pytest
from datetime import datetime
from app.repositories.message_repository import MessageRepository
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Chain, Message, User

@pytest.mark.asyncio
async def test_create_genesis_message(
    message_repo: MessageRepository,
    test_user: User,
    test_chain: Chain
):
    """Тест создания генезис сообщения"""
    message = await message_repo.create_genesis_message(
        chain_id=test_chain.id,
        sender_id=test_user.id,
        content="Genesis block",
        signature="test_signature"
    )
    
    assert message.id is not None
    assert message.block_height == 1
    assert message.prev_hash is None
    assert message.hash is not None

@pytest.mark.asyncio
async def test_add_message_to_chain(
    message_repo: MessageRepository,
    test_user: User,
    test_chain: Chain
):
    """Тест добавления сообщения в цепочку"""
    # Сначала создаем генезис
    genesis = await message_repo.create_genesis_message(
        chain_id=test_chain.id,
        sender_id=test_user.id,
        content="Genesis",
        signature="sig1"
    )
    
    # Добавляем второе сообщение
    message2 = await message_repo.add_message_to_chain(
        chain_id=test_chain.id,
        sender_id=test_user.id,
        content="Second message",
        signature="sig2",
        prev_hash=genesis.hash
    )
    
    assert message2.block_height == 2
    assert message2.prev_hash == genesis.hash
    
    # Добавляем третье
    message3 = await message_repo.add_message_to_chain(
        chain_id=test_chain.id,
        sender_id=test_user.id,
        content="Third message",
        signature="sig3",
        prev_hash=message2.hash
    )
    
    assert message3.block_height == 3
    assert message3.prev_hash == message2.hash

@pytest.mark.asyncio
async def test_validate_chain(
    message_repo: MessageRepository,
    test_user: User,
    test_chain: Chain
):
    """Тест валидации цепочки"""
    # Создаем цепочку из 3 сообщений
    genesis = await message_repo.create_genesis_message(
        test_chain.id, test_user.id, "Genesis", "sig1"
    )
    msg2 = await message_repo.add_message_to_chain(
        test_chain.id, test_user.id, "Second", "sig2", genesis.hash
    )
    msg3 = await message_repo.add_message_to_chain(
        test_chain.id, test_user.id, "Third", "sig3", msg2.hash
    )
    
    # Валидируем цепочку
    validation = await message_repo.validate_chain(test_chain.id)
    validation_list = list(validation)
    
    print("\n=== Результат валидации ===")
    for block_height, hash_val, prev_hash, links_valid, content_valid in validation_list:
        print(f"Block {block_height}: links_valid={links_valid}, content_valid={content_valid}")
    
    assert len(validation_list) == 3
    
    # Проверяем каждый блок
    # genesis
    assert validation_list[0][3] is True   # links_valid
    assert validation_list[0][4] is True   # content_valid
    
    # msg2
    assert validation_list[1][3] is True   # links_valid (prev_hash правильный)
    assert validation_list[1][4] is True   # content_valid (хеш соответствует содержимому)
    
    # msg3
    assert validation_list[2][3] is True   # links_valid (prev_hash правильный)
    assert validation_list[2][4] is True   # content_valid (хеш соответствует содержимому)

@pytest.mark.asyncio
async def test_validate_chain_with_invalid_message(
    message_repo: MessageRepository,
    test_user: User,
    test_chain: Chain
):
    """Тест валидации цепочки с невалидным сообщением"""
    # Создаем цепочку из 2 сообщений
    genesis = await message_repo.create_genesis_message(
        test_chain.id, test_user.id, "Genesis", "sig1"
    )
    msg2 = await message_repo.add_message_to_chain(
        test_chain.id, test_user.id, "Second", "sig2", genesis.hash
    )
    
    # "Портим" второе сообщение - меняем хеш
    msg2.hash = "tampered_hash"
    await message_repo.session.flush()
    await message_repo.session.refresh(msg2)
    
    # Валидируем цепочку
    validation = await message_repo.validate_chain(test_chain.id)
    validation_list = list(validation)
    
    print("\n=== Результат валидации испорченной цепочки ===")
    for block_height, hash_val, prev_hash, links_valid, content_valid in validation_list:
        print(f"Block {block_height}: links_valid={links_valid}, content_valid={content_valid}")
    
    assert len(validation_list) == 2
    
    # genesis: всё ок
    assert validation_list[0][3] is True   # links_valid
    assert validation_list[0][4] is True   # content_valid
    
    # msg2: links_valid=True (prev_hash правильный), content_valid=False (хеш изменен)
    assert validation_list[1][3] is True
    assert validation_list[1][4] is False
