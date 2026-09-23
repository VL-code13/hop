# ─────────────────────────────────────────────────────────────────────────────
# Этап 1: сборка зависимостей через Poetry
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV POETRY_VERSION=2.1.4 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Системные зависимости для сборки бинарных пакетов.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

# Сначала — только манифесты. Слой кешируется, пока зависимости не менялись.
COPY pyproject.toml poetry.lock ./

# Только prod-зависимости, без dev, без самого проекта.
RUN poetry install --only main --no-root --no-ansi

# ─────────────────────────────────────────────────────────────────────────────
# Этап 2: рантайм
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# В рантайме нужен только libpq — для psycopg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Готовое venv из builder-этапа.
COPY --from=builder /app/.venv /app/.venv

# Код проекта.
COPY . .

# Непривилегированный пользователь.
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Для прода — gunicorn. В docker-compose для dev переопределяется на runserver.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
