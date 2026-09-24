"""Конфигурация Celery для проекта Hop & Barley.

Celery — отдельный процесс, который забирает задачи из Redis и выполняет их.
Запускается командой `celery -A config worker -l info`.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('hop_and_barley')

# Читаем настройки Celery из Django settings с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находим tasks.py во всех приложениях
app.autodiscover_tasks()
