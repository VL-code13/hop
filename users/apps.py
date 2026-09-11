"""
Конфигурация приложения users для Django.
"""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """
    Класс конфигурации приложения пользователей.
    Регистрирует приложение в Django и подключает сигналы.
    """

    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'users'
    verbose_name: str = 'Пользователи и аккаунты'

    def ready(self) -> None:
        """
        Инициализация приложения при запуске сервера.
        Загружает сигналы создания профилей (по разделу 3.5 ТЗ).
        """
        import users.signals  # noqa: F401 «Module imported but unused» («Модуль импортирован, но не используется в коде»