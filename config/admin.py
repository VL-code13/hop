"""
Кастомный AdminSite с расширенной аналитикой и дашбордом продаж.

Реализует требования раздела 3.6 ТЗ («Админ-панель: аналитика: агрегаты,
аннотации, кастомная главная страница админки с метриками»).
"""

from decimal import Decimal
from typing import Any

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse

from orders.models import Order
from products.models import Product

User = get_user_model()


class HopBarleyAdminSite(admin.AdminSite):
    """Кастомный сайт панели администратора с расчетными бизнес-метриками."""

    site_header = 'Hop & Barley — Управление магазином'
    site_title = 'Панель администратора Hop & Barley'
    index_title = 'Аналитический дашборд и управление'
    index_template = 'admin/index.html'

    def index(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """
        Формирует контекст аналитического дашборда на главной странице админки.

        Использует ORM-агрегации (Sum, Count, Avg) по разделу 3.6 ТЗ.
        """
        extra_context = extra_context or {}

        # 1. Финансовые метрики
        sales_aggregate = Order.objects.filter(
            status__in=[Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED]
        ).aggregate(total_revenue=Sum('total_price'))
        total_sales = sales_aggregate['total_revenue'] or Decimal('0.00')

        # 2. Метрики по заказам
        total_orders_count = Order.objects.count()
        pending_orders_count = Order.objects.filter(status=Order.Status.PENDING).count()

        # 3. Пользователи
        total_users_count = User.objects.filter(is_active=True).count()

        # 4. Товары и склад
        total_products_count = Product.objects.filter(is_active=True).count()
        low_stock_products = Product.objects.filter(is_active=True, stock__lte=5).order_by('stock')[:5]

        # 5. Последние 5 заказов для быстрой модерации
        recent_orders = (
            Order.objects.select_related('user')
            .prefetch_related('items__product')
            .order_by('-created_at')[:5]
        )

        # Передаем агрегаты в контекст шаблона admin/index.html
        extra_context.update({
            'total_sales': total_sales,
            'total_orders_count': total_orders_count,
            'pending_orders_count': pending_orders_count,
            'total_users_count': total_users_count,
            'total_products_count': total_products_count,
            'low_stock_products': low_stock_products,
            'recent_orders': recent_orders,
        })

        return super().index(request, extra_context=extra_context)
