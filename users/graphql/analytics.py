"""Аналитические резолверы по пользователям.

Требование ТЗ 3.9: «Пользователи: активность, повторные покупки».

Повторный покупатель — пользователь с 2+ оплаченными заказами за период.
Это ключевая метрика удержания: рост доли повторных = продукт нравится.
"""

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Final

import strawberry
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from strawberry.types import Info

from config.graphql.cache import cache_metric
from config.graphql.permissions import staff_only
from orders.graphql.types import TrendPoint  # ← добавлено: импорт на уровне модуля
from orders.models import Order
from users.graphql.types import UserActivityMetrics

#: Статусы, при которых заказ считается «состоявшимся».
REVENUE_STATUSES: Final[list[str]] = [
    Order.Status.PAID,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
]

#: Минимальное количество заказов, чтобы считаться «повторным» покупателем.
REPEAT_THRESHOLD: Final[int] = 2

#: Длина периода по умолчанию.
DEFAULT_PERIOD_DAYS: Final[int] = 30


def _resolve_interval(interval: str) -> Callable[..., Any]:
    """Преобразует строку в Trunc-функцию для группировки по датам.

    Args:
        interval: 'day', 'week' или 'month'.

    Returns:
        Соответствующий Trunc-класс Django.

    Raises:
        ValueError: Если шаг неизвестен.
    """
    # ← mypy: возвращаемый тип object не callable. Callable[..., Any]
    #   позволяет вызвать результат как trunc('created_at').
    mapping: dict[str, Callable[..., Any]] = {'day': TruncDate, 'week': TruncWeek, 'month': TruncMonth}
    if interval not in mapping:
        raise ValueError(f'Неизвестный шаг: {interval!r}.')
    return mapping[interval]


def _resolve_date_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    """Нормализует диапазон дат; по умолчанию — последние 30 дней.

    Args:
        date_from: Начало или None.
        date_to: Конец или None.

    Returns:
        Кортеж (date_from, date_to).
    """
    today = timezone.localdate()
    if date_from is None and date_to is None:
        return today - timedelta(days=DEFAULT_PERIOD_DAYS - 1), today
    if date_from is None:
        assert date_to is not None
        return date_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1), date_to
    if date_to is None:
        return date_from, today
    return date_from, date_to


@strawberry.type
class UserAnalyticsQuery:
    """Аналитические запросы по пользователям (только staff)."""

    @strawberry.field
    @staff_only
    @cache_metric(ttl=300, prefix='users')
    def user_activity(
        self,
        info: Info,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> UserActivityMetrics:
        """Сводные метрики активности и удержания.

        Логика:
            1. Считаем новых пользователей по date_joined.
            2. Считаем уникальных покупателей — distinct user_id
               среди оплаченных заказов.
            3. Считаем повторных — тех, у кого 2+ таких заказов.

        Args:
            info: GraphQL-контекст.
            date_from: Начало периода.
            date_to: Конец периода.

        Returns:
            UserActivityMetrics.
        """
        d_from, d_to = _resolve_date_range(date_from, date_to)

        new_users = (
            get_user_model()
            .objects.filter(
                date_joined__date__gte=d_from,
                date_joined__date__lte=d_to,
            )
            .count()
        )

        paid_orders = Order.objects.filter(
            status__in=REVENUE_STATUSES,
            created_at__date__gte=d_from,
            created_at__date__lte=d_to,
        )

        per_user = paid_orders.values('user_id').annotate(orders=Count('id'))
        active_buyers = per_user.count()
        repeat_buyers = per_user.filter(orders__gte=REPEAT_THRESHOLD).count()

        repeat_rate = repeat_buyers / active_buyers if active_buyers else 0.0
        orders_per_buyer = paid_orders.count() / active_buyers if active_buyers else 0.0

        return UserActivityMetrics(
            new_users=new_users,
            active_buyers=active_buyers,
            repeat_buyers=repeat_buyers,
            repeat_purchase_rate=round(repeat_rate, 4),
            orders_per_buyer=round(orders_per_buyer, 2),
        )

    @strawberry.field
    @staff_only
    @cache_metric(ttl=600, prefix='users')
    def repeat_purchase_trend(
        self,
        info: Info,
        date_from: date | None = None,
        date_to: date | None = None,
        interval: str = 'month',
    ) -> list[TrendPoint]:  # ← убраны кавычки и # type: ignore
        """Динамика повторных покупок по интервалам.

        Для каждого интервала возвращаем количество пользователей,
        которые совершили 2+ заказа ЗА ЭТОТ интервал.

        Args:
            info: GraphQL-контекст.
            date_from: Начало периода.
            date_to: Конец периода.
            interval: 'day' | 'week' | 'month'.

        Returns:
            Список TrendPoint, где value — число повторных покупателей.
        """
        d_from, d_to = _resolve_date_range(date_from, date_to)
        trunc = _resolve_interval(interval)

        rows = (
            Order.objects.filter(
                status__in=REVENUE_STATUSES,
                created_at__date__gte=d_from,
                created_at__date__lte=d_to,
            )
            .annotate(period=trunc('created_at'))
            .values('period', 'user_id')
            .annotate(user_orders=Count('id'))
        )

        buckets: dict[date, set[int]] = {}
        for row in rows:
            if row['user_orders'] >= REPEAT_THRESHOLD:
                period = row['period'].date() if hasattr(row['period'], 'date') else row['period']
                buckets.setdefault(period, set()).add(row['user_id'])

        return [TrendPoint(period=period, value=float(len(users))) for period, users in sorted(buckets.items())]

    @strawberry.field
    @staff_only
    @cache_metric(ttl=300, prefix='users')
    def customer_lifetime_value(self, info: Info, user_id: strawberry.ID) -> Decimal:
        """Суммарная выручка от одного пользователя за всё время.

        LTV — накопительная метрика, поэтому не ограничиваем её периодом.

        Args:
            info: GraphQL-контекст.
            user_id: ID пользователя.

        Returns:
            Decimal — сумма total_price всех «заработанных» заказов.
        """
        total = Order.objects.filter(
            user_id=user_id,
            status__in=REVENUE_STATUSES,
        ).aggregate(total=Sum('total_price'))['total']
        return (total or Decimal('0.00')).quantize(Decimal('0.01'))
