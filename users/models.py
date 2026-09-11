"""
Модели базы данных для профилей покупателей.
Реализует требования разделов 3.5 («Личный кабинет») и 4 («Структура данных») ТЗ.
"""

from django.conf import settings
from django.db import models


class Profile(models.Model):
    """
    Профиль покупателя интернет-магазина.

    Связан отношением один-к-одному с User (раздел 4 ТЗ).
    Хранит телефон и адрес доставки для автозаполнения чекаута (раздел 3.4 и 3.5 ТЗ).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь',
        help_text='Учетная запись Django, к которой привязан профиль.',
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Номер телефона',
        help_text='Номер телефона для связи при доставке заказов.',
    )
    default_shipping_address = models.TextField(
        blank=True,
        verbose_name='Основной адрес доставки',
        help_text='Адрес доставки по умолчанию для подстановки в /checkout/.',
    )
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Аватар профиля',
        help_text='Изображение профиля покупателя.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания профиля',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата изменения профиля',
    )

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """Строковое представление профиля для админки (раздел 3.6 ТЗ)."""
        return f'Профиль пользователя {self.user.username}'