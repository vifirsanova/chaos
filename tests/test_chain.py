# tests/test_chain.py

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Chain, Message, User
from app.repositories.message_repository import MessageRepository
from datetime import datetime

@pytest.mark.asyncio
async def test_chain_integrity(db_session: AsyncSession, test_user: User):
    """Тест целостности цепочки"""
    repo = MessageRepository(db_session)
    
    chain = Chain(
        chain_type="test",
        chain_name="integrity_test"
    )
    db_session.add(chain)
    await db_session.flush()

    prev_hash = None
    for i in range(5):
        if i == 0:
            msg = await repo.create_genesis_message(
                chain.id, test_user.id, f"Msg {i}", f"sig{i}"
            )
        else:
            msg = await repo.add_message_to_chain(
                chain.id, test_user.id, f"Msg {i}", f"sig{i}", prev_hash
            )
        prev_hash = msg.hash

    result = await db_session.execute(
        select(Message)
        .where(Message.chain_id == chain.id)
        .order_by(Message.block_height)
    )
    messages = result.scalars().all()

    assert len(messages) == 5
    for i, msg in enumerate(messages):
        assert msg.block_height == i + 1

@pytest.mark.asyncio
async def test_chain_verification(db_session: AsyncSession, test_user: User):
    """Тест верификации цепочки хешей"""
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

    # Проверяем через новый метод validate_chain
    validation = await repo.validate_chain(chain.id)
    
    print("\n=== Проверка оригинальной цепочки через validate_chain ===")
    for block_height, hash_val, prev_hash, links_valid, content_valid in validation:
        print(f"Block {block_height}: links_valid={links_valid}, content_valid={content_valid}")
        assert links_valid is True
        assert content_valid is True

    # "Портим" цепочку - меняем хеш второго сообщения
    msg2.hash = "tampered_hash"
    await db_session.flush()
    await db_session.refresh(msg2)

    # Проверяем снова
    validation = await repo.validate_chain(chain.id)
    
    print("\n=== Проверка испорченной цепочки через validate_chain ===")
    for block_height, hash_val, prev_hash, links_valid, content_valid in validation:
        print(f"Block {block_height}: links_valid={links_valid}, content_valid={content_valid}")
    
    # genesis: всё ок
    assert validation[0][3] is True   # links_valid
    assert validation[0][4] is True   # content_valid
    
    # msg2: links_valid=True (prev_hash правильный), content_valid=False (хеш изменен)
    assert validation[1][3] is True
    assert validation[1][4] is False
    
    # msg3: links_valid=False (prev_hash ссылается на старый хеш), content_valid=True (свой хеш ок)
    assert validation[2][3] is False
    assert validation[2][4] is True

@pytest.mark.asyncio
async def test_chain_with_gap(db_session: AsyncSession, test_user: User):
    """Тест цепочки с пропуском"""
    repo = MessageRepository(db_session)
    chain = Chain(chain_type="test")
    db_session.add(chain)
    await db_session.flush()

    genesis = await repo.create_genesis_message(
        chain.id, test_user.id, "Genesis", "sig1"
    )

    bad_msg = await repo.add_message_to_chain(
        chain.id, 
        test_user.id, 
        "Bad message", 
        "sig2", 
        "wrong_prev_hash"
    )

    validation = await repo.validate_chain(chain.id)
    validation_list = list(validation)

    assert len(validation_list) == 2
    # genesis: всё ок
    assert validation_list[0][3] is True   # links_valid
    assert validation_list[0][4] is True   # content_valid
    # bad_msg: links_valid=False (неправильный prev_hash), content_valid зависит от содержимого
    assert validation_list[1][3] is False  # links_valid
    # content_valid может быть True или False в зависимости от хеша
