-- Функция для создания первого сообщения в цепочке
CREATE OR REPLACE FUNCTION create_genesis_message(
    p_chain_id BIGINT,
    p_sender_id BIGINT,
    p_content TEXT,
    p_hash TEXT,
    p_signature TEXT
) RETURNS BIGINT AS $$
DECLARE
    v_message_id BIGINT;
BEGIN
    INSERT INTO messages (
        hash, prev_hash, signature, chain_id, sender_id,
        content, block_height
    ) VALUES (
        p_hash, NULL, p_signature, p_chain_id, p_sender_id,
        p_content, 1
    ) RETURNING id INTO v_message_id;
    
    RETURN v_message_id;
END;
$$ LANGUAGE plpgsql;