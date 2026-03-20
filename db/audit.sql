-- Функция проверки: не дырявая ли цепочка
CREATE OR REPLACE FUNCTION validate_chain(p_chain_id BIGINT)
RETURNS TABLE(
    block_height BIGINT,
    hash TEXT,
    prev_hash TEXT,
    is_valid BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH ordered_messages AS (
        SELECT 
            m.block_height,
            m.hash,
            m.prev_hash,
            LAG(m.hash) OVER (ORDER BY m.block_height) as expected_prev
        FROM messages m
        WHERE m.chain_id = p_chain_id
        ORDER BY m.block_height
    )
    SELECT 
        block_height,
        hash,
        prev_hash,
        (prev_hash IS NULL AND block_height = 1) OR 
        (prev_hash = expected_prev) as is_valid
    FROM ordered_messages;
END;
$$ LANGUAGE plpgsql;