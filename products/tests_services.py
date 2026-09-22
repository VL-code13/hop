# products/tests_services.py
"""Тесты сервисного слоя каталога товаров (`products/services.py`).

Проверяют фильтрацию, поиск и сортировку без HTTP-клиента — быстро и
изолированно от шаблонов. Каждый тест пишет в БД (маркер `django_db`)
через фикстуры из `conftest.py`.
"""

from decimal import Decimal

import pytest

from products.services import get_catalog_queryset


@pytest.mark.django_db
class TestGetCatalogQueryset:
    """Набор тестов для `get_catalog_queryset`."""

    def test_only_active_products_by_default(self, product, inactive_product):
        """По умолчанию возвращаются только активные товары."""
        qs = get_catalog_queryset()
        assert product in qs
        assert inactive_product not in qs

    def test_default_sort_is_newest(self, product):
        """Без параметра sort применяется сортировка по `-created_at`."""
        qs = get_catalog_queryset()
        assert qs.first() == product

    def test_filter_by_category(self, product, category):
        """Фильтр по слагу категории возвращает только её товары."""
        qs = get_catalog_queryset(category_slug=category.slug)
        assert product in qs

    def test_filter_by_nonexistent_category_returns_empty(self, product):
        """Фильтр по несуществующему слагу → пустой QuerySet."""
        qs = get_catalog_queryset(category_slug='nonexistent')
        assert not qs.exists()

    def test_search_by_name(self, product):
        """Поиск по подстроке в имени товара."""
        qs = get_catalog_queryset(search_query=product.name[:4])
        assert product in qs

    def test_search_by_description(self, product):
        """Поиск по подстроке в описании товара."""
        qs = get_catalog_queryset(search_query=product.description[:5])
        assert product in qs

    def test_price_range(self, product):
        """Фильтр по диапазону цен включает товар с ценой внутри диапазона."""
        low = product.price - Decimal('100.00')
        high = product.price + Decimal('100.00')
        qs = get_catalog_queryset(min_price=str(low), max_price=str(high))
        assert product in qs

    def test_invalid_min_price_is_ignored(self, product):
        """Нечисловой `min_price` не роняет запрос, фильтр игнорируется."""
        qs = get_catalog_queryset(min_price='not-a-number')
        assert product in qs

    def test_invalid_max_price_is_ignored(self, product):
        """Нечисловой `max_price` не роняет запрос, фильтр игнорируется."""
        qs = get_catalog_queryset(max_price='abc')
        assert product in qs

    def test_sort_by_price_asc(self, product_factory):
        """Сортировка `price_asc` ставит дешёвый товар первым."""
        cheap = product_factory(price=Decimal('100.00'))
        product_factory(price=Decimal('500.00'))
        qs = get_catalog_queryset(sort='price_asc')
        assert qs.first() == cheap

    def test_sort_by_price_desc(self, product_factory):
        """Сортировка `price_desc` ставит дорогой товар первым."""
        product_factory(price=Decimal('100.00'))
        expensive = product_factory(price=Decimal('500.00'))
        qs = get_catalog_queryset(sort='price_desc')
        assert qs.first() == expensive

    def test_unknown_sort_falls_back_to_default(self, product):
        """Неизвестный sort не роняет запрос — используется дефолт."""
        qs = get_catalog_queryset(sort='bitcoin')
        assert product in qs
