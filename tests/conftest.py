import pytest
import pytest_asyncio
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Optional
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.database import Base
from app.models import User, Chain
from app.repositories.message_repository import MessageRepository

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5433/test_chaos"

# Simple function-scoped event loop for async fixtures
@pytest.fixture(scope="function")
def event_loop():
    """Create an event loop for each test function."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)

# Use function-scoped engine to avoid scope mismatch issues
@pytest_asyncio.fixture(scope="function")
async def engine(event_loop):
    """Create the SQLAlchemy engine for tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=True,
        future=True,
        pool_pre_ping=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await create_test_partitions(conn)
    
    yield engine
    
    await engine.dispose()

async def create_test_partitions(conn):
    """Create necessary table partitions for tests."""
    for i in range(3):
        month_date = datetime.utcnow() + timedelta(days=30 * i)
        month_str = month_date.strftime('%Y_%m')
        partition_name = f'messages_{month_str}'
        start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        
        # Check if partition exists before creating
        result = await conn.execute(text(f"""
            SELECT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = '{partition_name}'
            )
        """))
        exists = result.scalar()
        
        if not exists:
            await conn.execute(text(f"""
                CREATE TABLE {partition_name} PARTITION OF messages
                FOR VALUES FROM ('{start_date.isoformat()}') TO ('{end_date.isoformat()}')
            """))

@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Create a new database session for a test function."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session):
    """Create a test user."""
    user = User(pubkey="test_pubkey_123", username="tester")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def test_chain(db_session, test_user):
    """Create a test chain."""
    chain = Chain(chain_type="global", chain_name="test_chain")
    db_session.add(chain)
    await db_session.commit()
    await db_session.refresh(chain)
    return chain

@pytest_asyncio.fixture(scope="function")
async def message_repo(db_session):
    """Message repository fixture."""
    return MessageRepository(db_session)
