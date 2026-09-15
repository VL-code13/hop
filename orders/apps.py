"""Конфигурация приложения управления заказами и корзиной."""

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Класс настроек приложения orders."""

    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'orders'
    verbose_name: str = 'Заказы и корзина'
