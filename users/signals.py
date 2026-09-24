"""
Обработчики сигналов Django для поддержания целостности профилей.

Соответствует разделу 3.5 («Личный кабинет: регистрация») и разделу 6 ТЗ.

Сигнал post_save на модели User срабатывает каждый раз, когда
сохраняется пользователь (создание или обновление). Мы используем
флаг `created`, чтобы создать Profile только при первом сохранении —
при регистрации нового пользователя.
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
    Автоматическое создание профиля при регистрации нового пользователя.

    sender — класс модели, отправившей сигнал (модель User).
    instance — конкретный экземпляр сохранённого пользователя.
    created — True, если объект создан (первое сохранение); False — при обновлении.

    Профиль создаётся только при created=True, чтобы не дублировать
    при каждом сохранении пользователя (например, при смене email).

    instance типизирован как Model (базовый класс Django ORM).
    django-stubs не сужает тип через sender до User, поэтому
    # type: ignore[misc] заглушает ошибку mypy при передаче instance в
    Profile.objects.create(user=instance) — поле user ждёт User | Combinable.
    В рантайме instance — это полноценный объект User, всё работает корректно.
    """
    if created:
        Profile.objects.create(user=instance)  # type: ignore[misc]
