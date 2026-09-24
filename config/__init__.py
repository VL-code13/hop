"""Инициализация Celery при старте Django.

Импорт должен быть здесь, чтобы @shared_task работал в любом приложении.
"""

from config.celery import app as celery_app

__all__ = ('celery_app',)
