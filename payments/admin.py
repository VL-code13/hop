"""Регистрация моделей платежей в панели управления Django."""

from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Панель управления платежными транзакциями."""

    list_display = ('id', 'order', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('id', 'order__id', 'order__user__username', 'order__user__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
