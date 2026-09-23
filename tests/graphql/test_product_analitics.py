import pytest
from django.test import Client


@pytest.mark.django_db
def test_low_stock_products_respects_threshold(staff_token: str, product_factory) -> None:
    """Товары с остатком ниже порога попадают в отчёт."""
    product_factory(name='Almost Gone', stock=2)
    product_factory(name='Plenty', stock=50)

    response = Client().post(
        '/graphql/',
        data='{"query": "{ lowStockProducts(threshold: 5) { stock } }"}',
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {staff_token}',
    )
    items = response.json()['data']['lowStockProducts']
    assert len(items) == 1
    assert items[0]['stock'] == 2
