# tests/test_crypto.py

import pytest
import hashlib
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Chain, Message

@pytest.mark.asyncio
async def test_chain_validation(db_session: AsyncSession, test_user: User):
    """Тест полной валидации цепочки"""
    from app.repositories.message_repository import MessageRepository
    repo = MessageRepository(db_session)
    
    chain = Chain(chain_type="test", created_at=datetime.utcnow())
    db_session.add(chain)
    await db_session.flush()

    genesis = await repo.create_genesis_message(
        chain.id, test_user.id, "Genesis", "sig1"
    )
    msg2 = await repo.add_message_to_chain(
        chain.id, test_user.id, "Second", "sig2", genesis.hash
    )
    msg3 = await repo.add_message_to_chain(
        chain.id, test_user.id, "Third", "sig3", msg2.hash
    )

    # Проверяем полную валидацию
    validation = await repo.validate_chain(chain.id)
    
    print("\n=== Валидация оригинальной цепочки ===")
    for block_height, hash_val, prev_hash, links_valid, content_valid in validation:
        print(f"Block {block_height}: links_valid={links_valid}, content_valid={content_valid}")
        assert links_valid is True
        assert content_valid is True

    # Проверяем быструю валидацию
    assert await repo.is_chain_valid(chain.id) is True
    assert await repo.get_invalid_messages(chain.id) == []

    # "Портим" цепочку - меняем хеш второго сообщения
    msg2.hash = "tampered_hash"
    await db_session.flush()
    await db_session.refresh(msg2)

    # Проверяем снова
    validation = await repo.validate_chain(chain.id)
    
    print("\n=== Валидация испорченной цепочки ===")
    for block_height, hash_val, prev_hash, links_valid, content_valid in validation:
        print(f"Block {block_height}: links_valid={links_valid}, content_valid={content_valid}")
    
    # genesis: всё ок
    assert validation[0][3] is True   # links_valid
    assert validation[0][4] is True   # content_valid
    
    # msg2: links_valid=True (prev_hash правильный), content_valid=False (хес изменен)
    assert validation[1][3] is True
    assert validation[1][4] is False
    
    # msg3: links_valid=False (prev_hash ссылается на старый хеш), content_valid=True (свой хеш ок)
    assert validation[2][3] is False
    assert validation[2][4] is True

    # Проверяем быструю валидацию
    assert await repo.is_chain_valid(chain.id) is False
    
    # Проверяем получение проблемных сообщений
    invalid = await repo.get_invalid_messages(chain.id)
    print(f"\nПроблемные сообщения: {invalid}")
    assert len(invalid) == 2  # msg2 и msg3
