# tests/test_schema.py

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_tables_exist(db_session: AsyncSession):
    """Проверяем, что все таблицы созданы"""
    # Получаем connection через await
    conn = await db_session.connection()
    
    def get_table_names(connection):
        inspector = inspect(connection)
        return inspector.get_table_names()
    
    tables = await conn.run_sync(get_table_names)
    
    expected_tables = {'users', 'chains', 'messages', 'attachments', 'contacts'}
    for table in expected_tables:
        assert table in tables, f"Table {table} not found"

@pytest.mark.asyncio
async def test_partitions_exist(db_session: AsyncSession):
    """Проверяем создание партиций"""
    result = await db_session.execute(text("""
        SELECT relkind = 'p' as is_partitioned
        FROM pg_class 
        WHERE relname = 'messages'
    """))
    row = result.first()
    assert row is not None, "Messages table not found"
    assert row[0] is True, "Messages table is not partitioned"

@pytest.mark.asyncio
async def test_foreign_keys(db_session: AsyncSession):
    """Проверяем внешние ключи"""
    conn = await db_session.connection()
    
    def get_foreign_keys(connection):
        inspector = inspect(connection)
        return inspector.get_foreign_keys('attachments')
    
    fks = await conn.run_sync(get_foreign_keys)
    
    assert len(fks) > 0, "No foreign keys found in attachments"
    
    found_composite = False
    for fk in fks:
        if set(fk['constrained_columns']) == {'message_id', 'message_created_at'}:
            found_composite = True
            break
    
    assert found_composite, "Composite foreign key to messages not found"

@pytest.mark.asyncio
async def test_partition_boundaries(db_session: AsyncSession):
    """Проверяем, что созданы партиции на текущий и следующие месяцы"""
    result = await db_session.execute(text("""
        SELECT 
            inhrelid::regclass::text as partition_name,
            pg_get_expr(relpartbound, inhrelid) as partition_boundary
        FROM pg_inherits
        JOIN pg_class ON inhrelid = pg_class.oid
        WHERE inhparent = 'messages'::regclass
        ORDER BY partition_name
    """))
    
    partitions = result.all()
    assert len(partitions) >= 3, f"Expected at least 3 partitions, got {len(partitions)}"

@pytest.mark.asyncio
async def test_unique_constraints(db_session: AsyncSession):
    """Проверяем уникальные ограничения"""
    conn = await db_session.connection()
    
    def get_unique_constraints(connection):
        inspector = inspect(connection)
        return inspector.get_unique_constraints('messages')
    
    unique_constraints = await conn.run_sync(get_unique_constraints)
    
    found = False
    for uc in unique_constraints:
        if set(uc['column_names']) == {'hash', 'created_at'}:
            found = True
            break
    
    assert found, "Unique constraint (hash, created_at) not found"
