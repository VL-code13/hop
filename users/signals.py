"""
Обработчики сигналов Django для поддержания целостности профилей.
Соответствует разделу 3.5 («Личный кабинет: регистрация») и разделу 6 ТЗ.
"""

from typing import Any
from django.conf import settings
from django.db.models import Model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def auto_create_profile(
    sender: type[Model],
    instance: Model,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Автоматическое создание связанного Profile при регистрации пользователя.
    Устранена потенциальная рекурсия при обычном сохранении пользователя.
    """
    if created:
        Profile.objects.create(user=instance)