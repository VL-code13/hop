"""Конфигурация приложения управления платежами."""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Настройки приложения payments."""

    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'payments'
    verbose_name: str = 'Платежи и транзакции'
