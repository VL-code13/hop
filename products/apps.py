"""Конфигурация Django-приложения каталога товаров."""

from django.apps import AppConfig


class ProductsConfig(AppConfig):
    """Класс настроек приложения products."""

    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "products"
    verbose_name: str = "Каталог товаров"
