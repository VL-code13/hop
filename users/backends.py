"""
Кастомный бэкенд аутентификации.
Реализует раздел 2 («session-based аутентификация») и раздел 3.5 ТЗ:
- Покупатели входят на сайте по Email;
- Администраторы могут входить в /admin/ по системному имени (Username).
"""

from typing import Any, Optional
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Q
from django.http import HttpRequest

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Бэкенд аутентификации с поддержкой входа по email и username.
    Соответствует требованиям гибкой авторизации по разделу 3.5 ТЗ.
    """

    def authenticate(
        self,
        request: Optional[HttpRequest],
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[AbstractBaseUser]:
        """
        Поиск пользователя по email или username без учета регистра.
        Проверяет пароль и флаг активности (is_active=True).
        """
        login_credential: Optional[str] = username or kwargs.get('email')

        if not login_credential or not password:
            return None

        user = User.objects.filter(
            Q(email__iexact=login_credential) | Q(username__iexact=login_credential)
        ).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None