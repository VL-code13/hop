"""Регистрация моделей платежей в панели управления Django.

Поля транзакции не редактируются вручную — это защита от рассинхрона
с ``Order.status``. Статус меняется только через ``PaymentService``.
"""

from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Панель управления платежными транзакциями."""

    list_display = (
        'id',
        'order',
        'amount',
        'payment_method',
        'status',
        'created_at',
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = (
        'id',
        'order__id',
        'order__user__username',
        'order__user__email',
    )
    readonly_fields = (
        'id',
        'order',
        'amount',
        'payment_method',
        'status',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    def has_add_permission(self, request) -> bool:
        """Запрещает создание транзакции через админку.

        Транзакции создаются только через ``PaymentService.process_payment``,
        иначе нарушаются инварианты (уникальность SUCCESS, статус заказа).
        """
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Запрещает редактирование существующих транзакций.

        Финансовые записи не должны меняться после создания.
        """
        return False
