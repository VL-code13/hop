# Makefile для проекта Hop & Barley.
#
# Шорткаты для типовых команд. Все цели — thin-обёртки над poetry/docker.
# Отступы — ТАБУЛЯЦИЯ, не пробелы (иначе make падает с missing separator).
#
# Использование:
#   make help        — показать все доступные цели
#   make install     — установить зависимости + pre-commit хуки
#   make test        — быстрые тесты на SQLite
#   make ci          — полная симуляция CI перед push

.DEFAULT_GOAL := help
.PHONY: help install run shell migrate makemigrations test test-all test-graphql lint format ci \
        up down logs redis-cli psql flush-cache check cover clean

# ─────────────────────────────────────────────────────────────────────────────
# Помощь
# ─────────────────────────────────────────────────────────────────────────────

help:  ## Показать это сообщение
	@echo 'Hop & Barley — доступные команды:'
	@echo ''
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ─────────────────────────────────────────────────────────────────────────────
# Установка и запуск
# ─────────────────────────────────────────────────────────────────────────────

install:  ## Установить зависимости и pre-commit hooks
	poetry install
	poetry run pre-commit install
	poetry run pre-commit install --hook-type pre-push

run:  ## Запустить dev-сервер на 0.0.0.0:8000
	poetry run python manage.py runserver 0.0.0.0:8000

shell:  ## Открыть Django shell
	poetry run python manage.py shell

# ─────────────────────────────────────────────────────────────────────────────
# Миграции
# ─────────────────────────────────────────────────────────────────────────────

migrate:  ## Применить миграции
	poetry run python manage.py migrate

makemigrations:  ## Создать новые миграции
	poetry run python manage.py makemigrations

# ─────────────────────────────────────────────────────────────────────────────
# Тесты
# ─────────────────────────────────────────────────────────────────────────────

test:  ## Быстрые тесты на SQLite без coverage
	poetry run pytest --ds=config.settings.test --no-cov

test-all:  ## Полный прогон с coverage (как в CI)
	poetry run pytest --ds=config.settings.test --cov=. --cov-report=term-missing

test-graphql:  ## Только тесты GraphQL
	poetry run pytest tests/graphql/ --ds=config.settings.test --no-cov -v

test-products:  ## Только тесты каталога
	poetry run pytest products/ --ds=config.settings.test --no-cov -v

# ─────────────────────────────────────────────────────────────────────────────
# Линтеры и форматирование
# ─────────────────────────────────────────────────────────────────────────────

lint:  ## Проверить код (ruff + mypy) без изменений
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy .

format:  ## Автоформатирование и автофиксы
	poetry run ruff check . --fix
	poetry run ruff format .

# ─────────────────────────────────────────────────────────────────────────────
# CI: полная симуляция пайплайна
# ─────────────────────────────────────────────────────────────────────────────

ci:  ## Полная проверка как в CI перед push
	poetry check --lock
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy .
	poetry run python manage.py check
	poetry run python manage.py makemigrations --check --dry-run
	poetry run pytest --ds=config.settings.test --cov-fail-under=70

# ─────────────────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────────────────

up:  ## Поднять PostgreSQL и Redis
	docker compose up -d db redis

down:  ## Остановить все контейнеры
	docker compose down

logs:  ## Логи web-контейнера
	docker compose logs -f web

# ─────────────────────────────────────────────────────────────────────────────
# Отладка инфраструктуры
# ─────────────────────────────────────────────────────────────────────────────

redis-cli:  ## Открыть redis-cli
	redis-cli

psql:  ## Открыть psql в БД из docker-compose
	docker compose exec db psql -U $${POSTGRES_USER:-user} -d $${POSTGRES_DB:-hopbarley}

flush-cache:  ## Очистить весь кеш (Redis или LocMem)
	poetry run python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache cleared')"

# ─────────────────────────────────────────────────────────────────────────────
# Уборка
# ─────────────────────────────────────────────────────────────────────────────

clean:  ## Удалить артефакты (pycache, htmlcov, .pytest_cache, .mypy_cache)
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	@echo 'Cleaned.'
