"""Модели базы данных для системы пользовательских отзывов и рейтингов.
Реализует требования разделов 3.2 («Отзывы с рейтингами 1–5») и 4 («Структура данных») ТЗ.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from products.models import Product


class Review(models.Model):
    """
    Отзыв покупателя на приобретенный товар.

    Каждый пользователь может оставить только один отзыв на конкретный товар.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="Товар",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="Покупатель",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Оценка от 1 до 5",
    )
    comment = models.TextField(
        verbose_name="Текст отзыва",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'user'],
                name='unique_review_per_user',
            )
        ]

    def __str__(self) -> str:
        """Строковое представление отзыва."""
        return f"{self.user} -> {self.product} ({self.rating}/5)"
