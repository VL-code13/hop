"""Административная панель для работы с заказами и финансовой аналитикой."""

from typing import Sequence
from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Табличный блок позиций товаров внутри карточки заказа."""

    model = OrderItem
    extra = 0
    raw_id_fields = ('product',)
    fields = ('product', 'price', 'quantity', 'cost_display')
    readonly_fields = ('cost_display',)

    @admin.display(description="Сумма позиции")
    def cost_display(self, obj: OrderItem) -> str:
        """Отображает расчетную стоимость единицы в чеке."""
        if obj.pk:
            return f"{obj.get_cost()} ₽"
        return "—"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Управление заказами: фильтры, поиск, кастомные действия и аналитика (раздел 3.6 ТЗ)."""

    list_display: Sequence[str] = (
        'id',
        'user',
        'status',
        'payment_method',
        'total_items_count',
        'total_price',
        'created_at',
    )
    list_display_links: Sequence[str] = ('id', 'user')
    list_filter: Sequence[str] = ('status', 'payment_method', 'created_at')
    search_fields: Sequence[str] = ('id', 'user__username', 'shipping_address')
    readonly_fields: Sequence[str] = ('created_at', 'updated_at')
    inlines = [OrderItemInline]
    ordering: Sequence[str] = ('-created_at',)
    actions = ['mark_as_paid', 'mark_as_shipped']

    def get_queryset(self, request: HttpRequest) -> QuerySet[Order]:
        """Аннотация суммарного числа позиций в заказе для аналитики."""
        queryset = super().get_queryset(request)
        return queryset.annotate(items_count=Count('items'))

    @admin.display(description="Позиций", ordering='items_count')
    def total_items_count(self, obj: Order) -> int:
        """Количество наименований в заказе."""
        return getattr(obj, 'items_count', 0)

    @admin.action(description="Перевести выбранные заказы в статус 'Оплачен'")
    def mark_as_paid(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """Массовое подтверждение статуса оплаты."""
        queryset.update(status=Order.Status.PAID)

    @admin.action(description="Перевести выбранные заказы в статус 'Отправлен'")
    def mark_as_shipped(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """Массовый перевод заказов в статус отправленных покупателю."""
        queryset.update(status=Order.Status.SHIPPED)