"""Кастомный сайт панели администратора с аналитикой."""

from decimal import Decimal
from typing import Any

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpRequest
from django.template.response import TemplateResponse

from orders.models import Order
from products.models import Product

User = get_user_model()


class HopBarleyAdminSite(admin.AdminSite):
    """
    Расширенная панель управления с аналитическим дашбордом (раздел 3.6 ТЗ).
    """

    site_header = 'Hop & Barley — Панель управления'
    site_title = 'Hop & Barley Администрирование'
    index_title = 'Аналитика и управление магазином'
    index_template = 'admin/index.html'

    def index(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> TemplateResponse:
        """
        Переопределенный метод главной страницы админки с передачей метрик.
        """
        extra_context = extra_context or {}

        # 1. Суммарная выручка по оплаченным заказам
        paid_statuses = [Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED]
        total_sales = Order.objects.filter(status__in=paid_statuses).aggregate(
            total=Sum('total_price')
        )['total'] or Decimal('0.00')

        # 2. Метрики заказов
        total_orders_count = Order.objects.count()
        pending_orders_count = Order.objects.filter(status=Order.Status.PENDING).count()

        # 3. Метрики пользователей и каталога
        total_users_count = User.objects.filter(is_active=True).count()
        total_products_count = Product.objects.filter(is_active=True).count()

        # 4. Товары с низким остатком (менее 5 штук)
        low_stock_products = (
            Product.objects.filter(is_active=True, stock__lte=5)
            .select_related('category')
            .order_by('stock')[:5]
        )

        # 5. Последние 5 заказов
        recent_orders = (
            Order.objects.select_related('user')
            .order_by('-created_at')[:5]
        )

        # Заполняем контекст для шаблона admin/index.html
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
