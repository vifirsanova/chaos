#!/bin/bash
export PYTHONPATH="${PYTHONPATH}:${PWD}"

echo "Запускаем тестовую БД..."
docker-compose -f tests/docker-compose.test.yml up -d

echo "Ожидаем запуск БД (3 сек)..."
sleep 3

echo "Запускаем тесты..."
# Флаг --asyncio-mode можно убрать, если настроен pytest.ini
python -m pytest tests/test_chain.py tests/test_crypto.py -v

echo "Останавливаем тестовую БД..."
docker-compose -f tests/docker-compose.test.yml down
