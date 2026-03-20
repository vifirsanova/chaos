# app/repositories/message_repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from datetime import datetime
from app.models import Message
import hashlib
from typing import Optional, List, Tuple, Dict

class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _calculate_hash(self, content: str, prev_hash: Optional[str] = None) -> str:
        """Вычисление хеша сообщения"""
        data = f"{content}{prev_hash or ''}"
        return hashlib.sha256(data.encode()).hexdigest()

    async def create_genesis_message(
        self, 
        chain_id: int, 
        sender_id: int, 
        content: str,
        signature: str
    ) -> Message:
        """Создание первого сообщения в цепочке"""
        message_hash = self._calculate_hash(content, None)
        
        message = Message(
            hash=message_hash,
            prev_hash=None,
            signature=signature,
            chain_id=chain_id,
            sender_id=sender_id,
            content=content,
            block_height=1,
            created_at=datetime.utcnow()
        )
        
        self.session.add(message)
        await self.session.flush()
        return message

    async def add_message_to_chain(
        self,
        chain_id: int,
        sender_id: int,
        content: str,
        signature: str,
        prev_hash: str
    ) -> Message:
        """Добавление сообщения в существующую цепочку"""
        # Получаем последний block_height
        result = await self.session.execute(
            select(Message.block_height)
            .where(Message.chain_id == chain_id)
            .order_by(Message.block_height.desc())
            .limit(1)
        )
        last_height = result.scalar_one_or_none() or 0

        # Вычисляем хеш с учетом предыдущего
        message_hash = self._calculate_hash(content, prev_hash)

        message = Message(
            hash=message_hash,
            prev_hash=prev_hash,
            signature=signature,
            chain_id=chain_id,
            sender_id=sender_id,
            content=content,
            block_height=last_height + 1,
            created_at=datetime.utcnow()
        )

        self.session.add(message)
        await self.session.flush()
        return message

    async def validate_chain(self, chain_id: int) -> List[Tuple[int, str, Optional[str], bool, bool]]:
        """
        Полная валидация цепочки сообщений.
        
        Возвращает список кортежей:
        (block_height, hash, prev_hash, links_valid, content_valid)
        
        - links_valid: корректность связи с предыдущим сообщением
        - content_valid: соответствие хеша содержимому
        """
        # Получаем все сообщения цепочки, отсортированные по высоте
        result = await self.session.execute(
            select(Message)
            .where(Message.chain_id == chain_id)
            .order_by(Message.block_height)
        )
        messages = result.scalars().all()
        
        if not messages:
            return []
        
        validation_result = []
        prev_hash = None
        
        for i, msg in enumerate(messages):
            # Проверка 1: корректность ссылки на предыдущее сообщение
            if i == 0:  # genesis
                links_valid = (msg.prev_hash is None)
            else:
                links_valid = (msg.prev_hash == prev_hash)
            
            # Проверка 2: соответствие хеша содержимому
            expected_hash = self._calculate_hash(msg.content, msg.prev_hash)
            content_valid = (msg.hash == expected_hash)
            
            validation_result.append((
                msg.block_height,
                msg.hash,
                msg.prev_hash,
                links_valid,
                content_valid
            ))
            
            prev_hash = msg.hash
        
        return validation_result

    async def is_chain_valid(self, chain_id: int) -> bool:
        """
        Быстрая проверка: вся ли цепочка валидна.
        """
        validation = await self.validate_chain(chain_id)
        return all(links_valid and content_valid 
                  for _, _, _, links_valid, content_valid in validation)

    async def get_invalid_messages(self, chain_id: int) -> List[Dict]:
        """
        Получить список проблемных сообщений с описанием ошибок.
        """
        validation = await self.validate_chain(chain_id)
        invalid_messages = []
        
        for block_height, hash_val, prev_hash, links_valid, content_valid in validation:
            errors = []
            if not links_valid:
                errors.append("invalid_prev_hash_link")
            if not content_valid:
                errors.append("hash_mismatch")
            
            if errors:
                invalid_messages.append({
                    "block_height": block_height,
                    "hash": hash_val,
                    "prev_hash": prev_hash,
                    "errors": errors
                })
        
        return invalid_messages
