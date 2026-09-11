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
def auto_create_and_update_profile(
    sender: type[Model],
    instance: Model,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Сигнал post_save для модели User:
    - При регистрации нового аккаунта (created=True) автоматически создает связанный Profile.
    - При обновлении данных синхронно сохраняет Profile (раздел 3.5 ТЗ).
    """
    if created:
        Profile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()  # type: ignore[attr-defined]