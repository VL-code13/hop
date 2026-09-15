FROM python:3.12-slim

# Отключение записи .pyc файлов и буферизации вывода логов
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Установка системных зависимостей для сборки psycopg2, Pillow и сетевых утилит
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Оптимизация кеширования слоев pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода проекта
COPY . .

EXPOSE 8000

# Дефолтная команда запуска
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]