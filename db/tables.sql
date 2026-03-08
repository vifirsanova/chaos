-- =====================================================
-- ПОЛЬЗОВАТЕЛИ
-- =====================================================
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    pubkey TEXT UNIQUE NOT NULL,           -- идентификатор для блокчейн-логики
    username TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ,
    
    -- для поиска
    username_tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', COALESCE(username, ''))
    ) STORED
);

CREATE INDEX idx_users_pubkey ON users(pubkey);
CREATE INDEX idx_users_username_search ON users USING GIN(username_tsv);
CREATE INDEX idx_users_created ON users(created_at);

-- =====================================================
-- ЦЕПОЧКИ (логические группы сообщений)
-- =====================================================
CREATE TABLE chains (
    id BIGSERIAL PRIMARY KEY,
    chain_type TEXT NOT NULL CHECK (chain_type IN ('global', 'private', 'feed', 'myvoid')),
    -- для приватных цепочек: комбинация двух pubkey (отсортированных)
    participant1_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    participant2_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    -- для глобальных/публичных: имя цепочки
    chain_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- гарантируем уникальность диалога
    CONSTRAINT unique_dialog CHECK (
        (chain_type = 'private' AND participant1_id IS NOT NULL AND participant2_id IS NOT NULL 
         AND participant1_id < participant2_id) OR
        (chain_type != 'private')
    )
);

CREATE INDEX idx_chains_participants ON chains(participant1_id, participant2_id);
CREATE INDEX idx_chains_type ON chains(chain_type);

-- =====================================================
-- СООБЩЕНИЯ (партиционированные)
-- =====================================================
CREATE TABLE messages (
    id BIGSERIAL,
    
    -- криптографические данные
    hash TEXT NOT NULL,
    prev_hash TEXT,                        -- NULL для первого сообщения в цепочке
    signature TEXT NOT NULL,
    
    -- связи (числовые ID, не TEXT)
    chain_id BIGINT NOT NULL REFERENCES chains(id) ON DELETE CASCADE,
    sender_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- метаданные
    content TEXT NOT NULL,
    content_iv TEXT,                        -- для шифрования
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    block_height BIGINT,                    -- порядковый номер в цепочке
    
    -- технические поля
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    
    PRIMARY KEY (id, created_at)            -- для партиционирования
) PARTITION BY RANGE (created_at);

-- Индексы на базовой таблице (наследуются партициями)
CREATE INDEX idx_messages_hash ON messages(hash);
CREATE INDEX idx_messages_chain ON messages(chain_id, created_at DESC);
CREATE INDEX idx_messages_sender ON messages(sender_id, created_at DESC);
CREATE INDEX idx_messages_chain_block ON messages(chain_id, block_height);

-- Составной индекс для диалогов (ищет по chain_id, но chain_id уже покрывает)
-- Для полнотекстового поиска по сообщениям
ALTER TABLE messages ADD COLUMN content_tsv TSVECTOR 
    GENERATED ALWAYS AS (to_tsvector('russian', COALESCE(content, ''))) STORED;
CREATE INDEX idx_messages_search ON messages USING GIN(content_tsv);

-- =====================================================
-- ВЛОЖЕНИЯ
-- =====================================================
CREATE TABLE attachments (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    message_created_at TIMESTAMPTZ NOT NULL,  -- для связи с партицией
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    file_size BIGINT,
    mime_type TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    FOREIGN KEY (message_id, message_created_at) 
        REFERENCES messages(id, created_at) ON DELETE CASCADE
);

CREATE INDEX idx_attachments_message ON attachments(message_id);
CREATE INDEX idx_attachments_hash ON attachments(file_hash);

-- =====================================================
-- КОНТАКТЫ (для private)
-- =====================================================
CREATE TABLE contacts (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, contact_id)
);