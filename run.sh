#!/bin/bash

export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Останавливаем старые контейнеры
docker-compose -f tests/docker-compose.test.yml down -v 2>/dev/null

# Запускаем тестовую БД
docker-compose -f tests/docker-compose.test.yml up -d

# Ждем пока БД запустится
echo "Waiting for database..."
sleep 5

# Запускаем тесты с правильными параметрами
python -m pytest tests/ \
    -v \
    --tb=short \
    --maxfail=1 \
    --asyncio-mode=strict \
    -o log_cli=true \
    -o log_cli_level=INFO

# Останавливаем тестовую БД
docker-compose -f tests/docker-compose.test.yml down
