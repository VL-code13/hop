"""
Настройки отображения моделей каталога в административной панели Django.

Реализует требования раздела 3.6 ТЗ («Админ-панель: управление товарами,
категориями, аннотации, фильтры, кастомные actions»).
"""

from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Конфигурация админ-зоны для товарных категорий (раздел 3.6 ТЗ)."""

    list_display = (
        'name',
        'slug',
        'parent',
        'products_count',
        'created_at',
    )
    list_filter = ('parent',)
    search_fields = ('name', 'slug')
    # Автоматическое заполнение слага из названия при вводе в админке
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)

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

    list_display = (
        'name',
        'category',
        'price',
        'stock',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'category', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    # Быстрое редактирование остатка, цены и активности прямо в таблице списка
    list_editable = ('stock', 'price', 'is_active')
    # Добавлены оба временных поля в readonly
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    actions = ['make_active', 'make_inactive']

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        """Оптимизация запроса: подгрузка категории через JOIN (select_related)."""
        queryset = super().get_queryset(request)
        return queryset.select_related('category')

    @admin.action(description='Сделать выбранные товары активными')
    def make_active(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовый action для перевода товаров в статус активных на витрине."""
        updated_count = queryset.update(is_active=True)
        self.message_user(request, f'Активировано товаров: {updated_count}.')

    @admin.action(description='Снять выбранные товары с витрины')
    def make_inactive(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовый action для деактивации товаров (снятия с продажи)."""
        updated_count = queryset.update(is_active=False)
        self.message_user(request, f'Снято с витрины товаров: {updated_count}.')