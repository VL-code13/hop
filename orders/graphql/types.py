"""Типы GraphQL для заказов и аналитики продаж."""

from datetime import date
from decimal import Decimal

import strawberry
import strawberry_django

from orders.models import Order, OrderItem
from products.graphql.types import ProductType


@strawberry_django.type(OrderItem)
class OrderItemType:
    """Позиция заказа."""

    id: strawberry.ID
    quantity: strawberry.auto
    price: Decimal

    @strawberry.field
    def product(self, info: object) -> ProductType:
        """Товар, к которому относится позиция.

        DjangoOptimizerExtension сам подтянет product через select_related,
        так что N+1 здесь не случится.
        """
        return ProductType.product

    @strawberry.field
    def line_total(self) -> Decimal:
        """Стоимость строки: price * quantity."""
        return self.price * self.quantity


@strawberry_django.type(Order)
class OrderType:
    """Заказ пользователя."""

    id: strawberry.ID
    status: strawberry.auto
    total_price: Decimal
    created_at: strawberry.auto
    items: list[OrderItemType]


# ─── Аналитические агрегаты ───


@strawberry.type
class TrendPoint:
    """Одна точка временного ряда.

    Используется всеми трендами (заказы, пользователи, продукты),
    чтобы клиент обрабатывал их единообразно.

    Attributes:
        period: Начало интервала (день, начало недели или месяца).
        value: Значение метрики в этом интервале.
    """

    period: date
    value: float


@strawberry.type
class OrderMetrics:
    """Сводные метрики заказов за период."""

    total_revenue: Decimal
    order_count: int
    average_order_value: Decimal
    unique_customers: int
    cancelled_count: int


@strawberry.type
class OrderTrends:
    """Временные ряды метрик заказов."""

    revenue: list[TrendPoint]
    orders: list[TrendPoint]
    average_order_value: list[TrendPoint]
