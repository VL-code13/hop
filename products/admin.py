"""
Настройки отображения моделей каталога в административной панели Django.

Реализует требования раздела 3.6 ТЗ («Админ-панель: управление товарами,
категориями, аннотации, фильтры, кастомные actions»).
"""

from typing import Sequence
from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Конфигурация админ-зоны для товарных категорий (раздел 3.6 ТЗ)."""

    list_display: Sequence[str] = (
        'name',
        'slug',
        'parent',
        'products_count',
        'created_at',
    )
    list_filter: Sequence[str] = ('parent',)
    search_fields: Sequence[str] = ('name', 'slug')
    prepopulated_fields: dict[str, Sequence[str]] = {'slug': ('name',)}
    ordering: Sequence[str] = ('name',)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Category]:
        """
        Аннотация количества привязанных товаров для аналитики (раздел 3.6 ТЗ).
        Исключает N+1 запросов при отображении списка категорий.
        """
        queryset = super().get_queryset(request)
        return queryset.annotate(total_products=Count('products'))

    @admin.display(description='Кол-во товаров', ordering='total_products')
    def products_count(self, obj: Category) -> int:
        """Отображает вычисленное количество товаров в категории."""
        return getattr(obj, 'total_products', 0)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Конфигурация админ-зоны для управления товарами (раздел 3.6 ТЗ)."""

    list_display: Sequence[str] = (
        'name',
        'category',
        'price',
        'stock',
        'is_active',
        'created_at',
    )
    list_filter: Sequence[str] = ('is_active', 'category', 'created_at')
    search_fields: Sequence[str] = ('name', 'description')
    prepopulated_fields: dict[str, Sequence[str]] = {'slug': ('name',)}
    list_editable: Sequence[str] = ('stock', 'price', 'is_active')
    readonly_fields: Sequence[str] = ('created_at',)
    date_hierarchy: str = 'created_at'
    actions: list[str] = ['make_active', 'make_inactive']

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        """Оптимизация запроса: select_related для категории."""
        queryset = super().get_queryset(request)
        return queryset.select_related('category')

    @admin.action(description='Сделать выбранные товары активными')
    def make_active(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовый action для перевода товаров в статус активных на витрине."""
        updated_count = queryset.update(is_active=True)
        self.message_user(request, f'Активировано товаров: {updated_count}.')

    @admin.action(description='Снять выбранные товары с витрины')
    def make_inactive(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовый action для деактивации товаров."""
        updated_count = queryset.update(is_active=False)
        self.message_user(request, f'Снято с витрины товаров: {updated_count}.')
