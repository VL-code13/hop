"""Тесты расчёта метрик заказов."""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_order_metrics_calculates_correctly(staff_token: str, order_factory) -> None:
    """Выручка и средний чек считаются по оплаченным, отменённые не в счёте."""
    # Товар в фикстуре стоит 500 ₽, quantity=1 → total_price = 500.
    order_factory(status='paid')
    order_factory(status='paid')
    order_factory(status='cancelled')

    response = Client().post(
        '/graphql/',
        data=('{"query": "{ orderMetrics { totalRevenue orderCount averageOrderValue cancelledCount } }"}'),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {staff_token}',
    )
    metrics = response.json()['data']['orderMetrics']

    assert metrics['orderCount'] == 2
    assert metrics['cancelledCount'] == 1
    assert metrics['totalRevenue'] == '1000.00'
    assert metrics['averageOrderValue'] == '500.00'


@pytest.mark.django_db
def test_order_trends_returns_daily_points(staff_token: str, order_factory) -> None:
    """Тренд по заказам возвращает хотя бы одну точку при наличии заказов."""
    order_factory(status='paid')
    order_factory(status='paid')

    response = Client().post(
        '/graphql/',
        data='{"query": "{ orderTrends(interval: \\"day\\") { orders { period value } } }"}',
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {staff_token}',
    )
    trends = response.json()['data']['orderTrends']
    assert len(trends['orders']) >= 1
    # Сегодняшний заказ → одна точка с value=2.
    assert trends['orders'][-1]['value'] == 2.0
