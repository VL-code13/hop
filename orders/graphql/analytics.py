"""Аналитические резолверы по заказам.

Требование ТЗ 3.9: «Заказы: выручка, количество, средний чек, тренды».

Ключевая идея: все агрегаты считаются на стороне БД через ORM-функции
Sum / Count / Avg / Trunc. Никаких питоновских переборов заказов.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Final

import strawberry
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from strawberry.types import Info

from config.graphql.cache import cache_metric
from config.graphql.permissions import staff_only
from orders.graphql.types import OrderMetrics, OrderTrends, TrendPoint
from orders.models import Order

#: Статусы, при которых заказ считается «заработанным».
#: ПРОВЕРЬТЕ, что эти значения совпадают с Order.Status в вашей модели.
REVENUE_STATUSES: Final[list[str]] = [
    Order.Status.PAID,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
]
#: Длина периода по умолчанию, если клиент не передал даты.
DEFAULT_PERIOD_DAYS: Final[int] = 30

#: Шаг агрегации по умолчанию для трендов.
DEFAULT_INTERVAL: Final[str] = 'day'


def _resolve_interval(interval: str) -> object:
    """Преобразует строковый шаг в Trunc-функцию Django.

    Args:
        interval: 'day', 'week' или 'month'.

    Returns:
        Класс TruncDate / TruncWeek / TruncMonth.

    Raises:
        ValueError: Если шаг неизвестен.
    """
    mapping = {'day': TruncDate, 'week': TruncWeek, 'month': TruncMonth}
    if interval not in mapping:
        raise ValueError(f'Неизвестный шаг агрегации: {interval!r}. Допустимо: {list(mapping)}.')
    return mapping[interval]


def _resolve_date_range(
        date_from: date | None,
        date_to: date | None,
) -> tuple[date, date]:
    """Нормализует входной диапазон дат.

    Если ничего не передано — берём последние DEFAULT_PERIOD_DAYS дней
    (включительно с сегодня). Если передан только date_to — считаем от
    него назад. Если только date_from — до сегодня.

    Args:
        date_from: Начало периода или None.
        date_to: Конец периода или None.

    Returns:
        Кортеж (date_from, date_to).
    """
    today = timezone.localdate()
    if date_from is None and date_to is None:
        return today - timedelta(days=DEFAULT_PERIOD_DAYS - 1), today
    if date_from is None:
        # date_to не может быть None здесь, но mypy нужно помочь.
        assert date_to is not None
        return date_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1), date_to
    if date_to is None:
        return date_from, today
    return date_from, date_to


@strawberry.type
class OrderAnalyticsQuery:
    """Аналитические запросы по заказам (только staff)."""

    @strawberry.field
    @staff_only
    @cache_metric(ttl=300,prefix='orders')  # 5 minutes
    def order_metrics(
            self,
            info: Info,
            date_from: date | None = None,
            date_to: date | None = None,
    ) -> OrderMetrics:
        """Сводные метрики заказов за период.

        Возвращает:
            - total_revenue — сумма total_price по «заработанным» статусам;
            - order_count — количество таких заказов;
            - average_order_value — total_revenue / order_count;
            - unique_customers — уникальные user_id;
            - cancelled_count — отдельно отменённые заказы.

        Все метрики, кроме cancelled_count, считаются ОДНИМ SQL-запросом
        через .aggregate(...). Отменённые — отдельным count(), потому что
        они в другой выборке.

        Args:
            info: GraphQL-контекст.
            date_from: Начало периода (опционально).
            date_to: Конец периода (опционально).

        Returns:
            OrderMetrics со всеми полями.
        """
        d_from, d_to = _resolve_date_range(date_from, date_to)

        # Базовая выборка: заказы со «заработанным» статусом за период.
        paid_orders = Order.objects.filter(
            status__in=REVENUE_STATUSES,
            created_at__date__gte=d_from,
            created_at__date__lte=d_to,
        )

        # Один запрос — три метрики. Это критично: на больших объёмах
        # отдельные запросы на каждую метрику дают заметный оверхед.
        agg = paid_orders.aggregate(
            total_revenue=Sum('total_price'),
            order_count=Count('id'),
            unique_customers=Count('user_id', distinct=True),
        )

        # Квантизация до 2 знаков после запятой. Без неё str(Decimal('1000'))
        # вернёт '1000', а клиент ожидает '1000.00' — фиксированный денежный формат.
        two_places = Decimal('0.01')
        total_revenue = (agg['total_revenue'] or Decimal('0.00')).quantize(two_places)
        order_count = agg['order_count'] or 0
        avg = (total_revenue / order_count).quantize(two_places) if order_count else Decimal('0.00')
        # Отменённые считаем отдельно — они не входят в выручку.
        cancelled = Order.objects.filter(
            status='cancelled',
            created_at__date__gte=d_from,
            created_at__date__lte=d_to,
        ).count()

        return OrderMetrics(
            total_revenue=total_revenue,
            order_count=order_count,
            average_order_value=avg,
            unique_customers=agg['unique_customers'] or 0,
            cancelled_count=cancelled,
        )

    @strawberry.field
    @staff_only
    @cache_metric(ttl=300, prefix='orders')
    def order_trends(
            self,
            info: Info,
            date_from: date | None = None,
            date_to: date | None = None,
            interval: str = DEFAULT_INTERVAL,
    ) -> OrderTrends:
        """Динамика заказов по интервалам.

        Возвращает три ряда одновременно (выручка, количество заказов,
        средний чек) — это дешевле, чем три отдельных запроса, потому
        что используется один GROUP BY.

        Args:
            info: GraphQL-контекст.
            date_from: Начало периода.
            date_to: Конец периода.
            interval: 'day' | 'week' | 'month'.

        Returns:
            OrderTrends с тремя списками TrendPoint.
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
            .values('period')
            .annotate(
                revenue=Sum('total_price'),
                orders=Count('id'),
                avg=Avg('total_price'),
            )
            .order_by('period')
        )

        revenue_points: list[TrendPoint] = []
        order_points: list[TrendPoint] = []
        avg_points: list[TrendPoint] = []

        for row in rows:
            # row['period'] — datetime, приводим к date, чтобы GraphQL-скаляр
            # date сериализовался корректно.
            period = row['period'].date() if hasattr(row['period'], 'date') else row['period']
            revenue_points.append(TrendPoint(period=period, value=round(float(row['revenue'] or 0), 2)))
            order_points.append(TrendPoint(period=period, value=float(row['orders'] or 0)))
            avg_points.append(TrendPoint(period=period, value=round(float(row['avg'] or 0), 2)))

        return OrderTrends(
            revenue=revenue_points,
            orders=order_points,
            average_order_value=avg_points,
        )
