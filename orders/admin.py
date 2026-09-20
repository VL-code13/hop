"""
Административная панель для управления заказами и финансовой аналитикой.

Реализует требования раздела 3.6 ТЗ («Управление заказами, аналитика: агрегаты,
аннотации, кастомные actions, фильтры»).
"""

from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, QuerySet, Sum
from django.http import HttpRequest

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Табличный блок товарных позиций чека внутри карточки заказа."""

    model = OrderItem
    extra = 0
    raw_id_fields = ('product',)
    fields = ('product', 'price', 'quantity', 'cost_display')
    # price — снимок цены на момент покупки, нельзя менять задним числом
    readonly_fields = ('price', 'cost_display')

    @admin.display(description='Сумма позиции')
    def cost_display(self, obj: OrderItem) -> str:
        """Отображает расчетную стоимость единицы в чеке."""
        if obj.pk:
            return f'{obj.get_cost()} ₽'
        return '—'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Управление заказами: фильтры, поиск, кастомные действия и аналитика (раздел 3.6 ТЗ)."""

    list_display = (
        'id',
        'user',
        'status',
        'payment_method',
        'total_items_count',
        'total_price',
        'created_at',
    )
    list_display_links = ('id', 'user')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('id', 'user__username', 'user__email', 'shipping_address')
    # total_price — вычисляемое финансовое поле, не редактируется руками
    readonly_fields = ('created_at', 'updated_at', 'total_price')
    raw_id_fields = ('user',)
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]
    ordering = ('-created_at',)
    actions = ['mark_as_paid', 'mark_as_shipped', 'show_revenue']

    def get_queryset(self, request: HttpRequest) -> QuerySet[Order]:
        """Аннотация суммарного числа позиций в заказе для быстрой аналитики."""
        queryset = super().get_queryset(request)
        return queryset.annotate(items_count=Count('items'))

    @admin.display(description='Позиций', ordering='items_count')
    def total_items_count(self, obj: Order) -> int:
        """Количество наименований в заказе."""
        return getattr(obj, 'items_count', 0)

    @admin.action(description="Перевести выбранные заказы в статус 'Оплачен'")
    def mark_as_paid(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """
        Массовое подтверждение статуса оплаты.

        Разрешает переход только из статуса PENDING.
        Заказы в CANCELLED/PAID/SHIPPED/DELIVERED не переводятся.
        """
        eligible = queryset.filter(status=Order.Status.PENDING)
        skipped = queryset.count() - eligible.count()
        updated = eligible.update(status=Order.Status.PAID)
        msg = f'Переведено в статус «Оплачен»: {updated} заказов.'
        if skipped:
            msg += f' Пропущено (не в статусе «Ожидает оплаты»): {skipped}.'
        self.message_user(request, msg)

    @admin.action(description="Отметить выбранные как 'Отправленные'")
    def mark_as_shipped(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """
        Массовый перевод заказов в статус отправленных покупателю.

        Разрешает переход только из статуса PAID.
        Заказы в CANCELLED/PENDING/SHIPPED/DELIVERED не переводятся.
        """
        eligible = queryset.filter(status=Order.Status.PAID)
        skipped = queryset.count() - eligible.count()
        updated = eligible.update(status=Order.Status.SHIPPED)
        msg = f'Переведено в статус «Отправлен»: {updated} заказов.'
        if skipped:
            msg += f' Пропущено (не в статусе «Оплачен»): {skipped}.'
        self.message_user(request, msg)

    @admin.action(description='Показать выручку по выбранным заказам')
    def show_revenue(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """
        Считает суммарную выручку по выбранным заказам с разбивкой по статусам.

        В выручку включаются только оплаченные заказы (PAID, SHIPPED, DELIVERED).
        Заказы в PENDING и CANCELLED не учитываются — деньги по ним не поступили.
        """
        paid_statuses = [
            Order.Status.PAID,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        ]
        paid_orders = queryset.filter(status__in=paid_statuses)
        unpaid_orders = queryset.exclude(status__in=paid_statuses)

        total_revenue: Decimal = paid_orders.aggregate(
            total=Sum('total_price'),
        )['total'] or Decimal('0.00')

        lines = [
            f'Выручка по выбранным заказам: {total_revenue} ₽',
            f'Учтено оплаченных заказов: {paid_orders.count()} шт.',
        ]

        for status_value, status_label in Order.Status.choices:
            count = paid_orders.filter(status=status_value).count()
            if count:
                subtotal = paid_orders.filter(
                    status=status_value,
                ).aggregate(sub=Sum('total_price'))['sub'] or Decimal('0.00')
                lines.append(f'  • {status_label}: {count} заказов, {subtotal} ₽')

        if unpaid_orders.exists():
            lines.append(f'Исключено (PENDING/CANCELLED): {unpaid_orders.count()} заказов.')

        self.message_user(request, '\n'.join(lines))
