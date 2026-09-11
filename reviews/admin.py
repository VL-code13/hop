"""Административная панель для модерации отзывов покупателей."""
from typing import Sequence
from django.contrib import admin

from reviews.models import Review


# Register your models here.

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Конфигурация админ-зоны для управления отзывами."""

    list_display: Sequence[str] = ('id', 'user', 'product', 'rating', 'created_at')
    list_filter: Sequence[str] = ('user','product', 'rating', 'created_at')
    search_fields: Sequence[str] = ('user__username', 'product__name', 'comment')
    readonly_fields: Sequence[str] = ('created_at',)
    ordering: Sequence[str] = ('-created_at',)