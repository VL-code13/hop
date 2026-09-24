"""
Административная панель для управления заказами и финансовой аналитикой.

Реализует требования раздела 3.6 ТЗ («Управление заказами, аналитика: агрегаты,
аннотации, кастомные actions, фильтры»).
"""

from decimal import Decimal
from typing import Any

from django.contrib import admin
from django.db.models import Count, QuerySet, Sum
from django.http import HttpRequest

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """Табличный блок товарных позиций чека внутри карточки заказа.

    Поле ``price`` — snapshot цены на момент покупки, оно readonly
    для существующих позиций (нельзя менять задним числом).

    При удалении позиции (чекбокс «Удалить») срабатывает
    ``OrderItem.delete()`` — он возвращает остаток товара на склад
    (кроме статусов DELIVERED/CANCELLED) и пересчитывает
    ``Order.total_price``.
    """

    model = OrderItem
    extra = 1  # одна пустая строка для добавления новой позиции
    autocomplete_fields = ('product',)
    fields = ('product', 'price', 'quantity', 'cost_display')
    readonly_fields = ('price', 'cost_display')

    @admin.display(description='Сумма позиции')
    def cost_display(self, obj: OrderItem) -> str:
        """Отображает расчётную стоимость единицы в чеке."""
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
    readonly_fields = ('created_at', 'updated_at', 'total_price', 'total_cost_live')
    autocomplete_fields = ('user',)
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]
    ordering = ('-created_at',)
    actions = ['mark_as_paid', 'mark_as_shipped', 'show_revenue']

    fieldsets = (
        (
            None,
            {
                'fields': ('user', 'status', 'payment_method', 'shipping_address'),
            },
        ),
        (
            'Финансы',
            {
                'fields': ('total_price', 'total_cost_live'),
            },
        ),
        (
            'Служебное',
            {
                'fields': ('created_at', 'updated_at'),
            },
        ),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Order]:
        """Аннотация суммарного числа позиций в заказе для быстрой аналитики."""
        queryset = super().get_queryset(request)
        return queryset.annotate(items_count=Count('items'))

    @admin.display(description='Позиций', ordering='items_count')
    def total_items_count(self, obj: Order) -> int:
        """Количество наименований в заказе."""
        return getattr(obj, 'items_count', 0)

    @admin.display(description='Сумма по позициям (актуально)')
    def total_cost_live(self, obj: Order) -> str:
        """Актуальная сумма, посчитанная по текущим позициям.

        Отображается рядом с сохранённым ``total_price`` — удобно
        сравнить, не разошлись ли они после ручной правки в админке.
        """
        if obj.pk:
            return f'{obj.get_total_cost()} ₽'
        return '—'

    def save_formset(
        self,
        request: HttpRequest,
        form: Any,
        formset: Any,
        change: bool,
    ) -> None:
        """Явно сохраняет inline-формы, подставляя ``price`` для новых позиций.

        Django внутри вызывает ``formset.save()``, который идёт в
        ``ModelForm.save()`` → ``instance.save()``. Если по какой-то
        причине ``OrderItem.save()`` не подставил цену (например,
        из-за особенностей inline-форм), здесь мы это делаем явно:

        1. ``formset.save(commit=False)`` — подготовка объектов без записи в БД.
        2. Для каждого — подставляем ``price``, если не задан.
        3. Сохраняем по одному, вызывая ``OrderItem.save()``.
        4. Удаляем отмеченные чекбоксом позиции — ``OrderItem.delete()``
           вернёт остаток на склад и пересчитает ``total_price``.
        5. Вызываем ``save_m2m`` (на будущее, если появятся M2M-поля).
        6. Пересчитываем ``Order.total_price`` — на случай, если позиции
           были только добавлены или изменены без удаления.
        """
        instances = formset.save(commit=False)

        for instance in instances:
            # Автозаполнение для новых позиций, добавленных через админку.
            # Поле `price` — readonly, Django его не передаёт в форму.
            if not instance.price and instance.product_id:
                instance.price = instance.product.price
            instance.save()

        # Удаление позиций, отмеченных чекбоксом «Удалить».
        # OrderItem.delete() вернёт остаток на склад (если статус позволяет)
        # и пересчитает total_price заказа.
        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m()

        # Финальный пересчёт суммы — на случай, если удалений не было,
        # но количество в существующих позициях изменилось.
        order: Order = form.instance  # type: ignore[attr-defined]
        order.recalculate_total()

    @admin.action(description="Перевести выбранные заказы в статус 'Оплачен'")
    def mark_as_paid(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """Массовое подтверждение статуса оплаты (только из PENDING)."""
        eligible = queryset.filter(status=Order.Status.PENDING)
        skipped = queryset.count() - eligible.count()
        updated = eligible.update(status=Order.Status.PAID)
        msg = f'Переведено в статус «Оплачен»: {updated} заказов.'
        if skipped:
            msg += f' Пропущено (не в статусе «Ожидает оплаты»): {skipped}.'
        self.message_user(request, msg)

    @admin.action(description="Отметить выбранные как 'Отправленные'")
    def mark_as_shipped(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """Массовый перевод заказов в статус отправленных (только из PAID)."""
        eligible = queryset.filter(status=Order.Status.PAID)
        skipped = queryset.count() - eligible.count()
        updated = eligible.update(status=Order.Status.SHIPPED)
        msg = f'Переведено в статус «Отправлен»: {updated} заказов.'
        if skipped:
            msg += f' Пропущено (не в статусе «Оплачен»): {skipped}.'
        self.message_user(request, msg)

    @admin.action(description='Показать выручку по выбранным заказам')
    def show_revenue(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        """Считает суммарную выручку по выбранным заказам с разбивкой по статусам."""
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
