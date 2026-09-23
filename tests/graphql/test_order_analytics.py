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
        data=(
            '{"query": "{ orderMetrics {'
            ' totalRevenue orderCount averageOrderValue cancelledCount'
            ' } }"}'
        ),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {staff_token}',
    )
    metrics = response.json()['data']['orderMetrics']

    assert metrics['orderCount'] == 2
    assert metrics['cancelledCount'] == 1
    assert metrics['totalRevenue'] == '1000.00'
    assert metrics['averageOrderValue'] == '500.00'
