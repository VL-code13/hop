"""
Административная панель для модерации отзывов покупателей.

Реализует требования раздела 3.6 ТЗ («Управление отзывами, фильтры, поиск»).
"""

from collections.abc import Sequence

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
    list_filter: Sequence[str] = ('rating', 'created_at', 'product__category')
    search_fields: Sequence[str] = ('user__username', 'user__email', 'product__name', 'comment')
    # product и user не редактируются — иначе сломается UniqueConstraint
    # и связь отзыва с реальной покупкой
    readonly_fields: Sequence[str] = ('product', 'user', 'created_at')
    raw_id_fields: Sequence[str] = ('product', 'user')
    date_hierarchy: str = 'created_at'
    ordering: Sequence[str] = ('-created_at',)
