"""Конфигурация приложения управления отзывами покупателей."""

from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    """Класс настроек приложения reviews."""

    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'reviews'
    verbose_name: str = 'Отзывы и рейтинги'