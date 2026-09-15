"""
Административная панель для модерации отзывов покупателей.

Реализует требования раздела 3.6 ТЗ («Управление отзывами, фильтры, поиск»).
"""

from typing import Sequence
from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Конфигурация админ-зоны для управления и модерации отзывов."""

    list_display: Sequence[str] = (
        'id',
        'user',
        'product',
        'rating',
        'created_at',
    )
    list_filter: Sequence[str] = ('rating', 'created_at', 'product')
    search_fields: Sequence[str] = ('user__username', 'user__email', 'product__name', 'comment')
    readonly_fields: Sequence[str] = ('created_at',)
    ordering: Sequence[str] = ('-created_at',)
