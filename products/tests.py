from django.test import TestCase

# Create your tests here.
"""
Модульные тесты приложения products.

Реализует требования разделов 6.3 («Тестирование: каталог, поиск, бизнес-правила») и 8 ТЗ.
"""

from decimal import Decimal
from django.urls import reverse
from products.models import Category, Product


class ProductCatalogTestCase(TestCase):
    """Набор тестов для проверки витрины, поиска, фильтров и карточки товара."""

    def setUp(self) -> None:
        """Инициализация тестовых данных перед каждым тестом."""
        self.category_hops = Category.objects.create(name='Хмель', slug='hops')
        self.category_malts = Category.objects.create(name='Солод', slug='malts')

        self.product_active = Product.objects.create(
            name='Citra Hops',
            slug='citra-hops',
            description='Яркий цитрусовый аромат грейпфрута и лайма.',
            price=Decimal('550.00'),
            category=self.category_hops,
            stock=15,
            is_active=True,
        )
        self.product_out_of_stock = Product.objects.create(
            name='Pilsner Malt',
            slug='pilsner-malt',
            description='Светлый базовый ячменный солод.',
            price=Decimal('200.00'),
            category=self.category_malts,
            stock=0,
            is_active=True,
        )
        self.product_hidden = Product.objects.create(
            name='Скрытый товар',
            slug='hidden-product',
            description='Снят с продажи.',
            price=Decimal('100.00'),
            category=self.category_hops,
            stock=10,
            is_active=False,
        )

    def test_catalog_displays_only_active_products(self) -> None:
        """Каталог отображает только активные товары (is_active=True)."""
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Citra Hops')
        self.assertContains(response, 'Pilsner Malt')
        self.assertNotContains(response, 'Скрытый товар')

    def test_filter_by_category_slug(self) -> None:
        """Фильтрация товаров по URL-категории возвращает только релевантные товары."""
        response = self.client.get(reverse('products:list_by_category', kwargs={'category_slug': 'hops'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Citra Hops')
        self.assertNotContains(response, 'Pilsner Malt')

    def test_search_by_query_string(self) -> None:
        """Поиск по подстроке в названии или описании (параметр q)."""
        response = self.client.get(reverse('products:list'), {'q': 'грейпфрут'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Citra Hops')
        self.assertNotContains(response, 'Pilsner Malt')

    def test_filter_by_price_range(self) -> None:
        """Фильтрация по минимальной и максимальной цене."""
        response = self.client.get(reverse('products:list'), {'min_price': '300', 'max_price': '600'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Citra Hops')
        self.assertNotContains(response, 'Pilsner Malt')

    def test_product_detail_view_and_stock_property(self) -> None:
        """Детальная страница открывается и корректно рассчитывает свойство in_stock."""
        response = self.client.get(reverse('products:detail', kwargs={'slug': 'citra-hops'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Citra Hops')
        self.assertContains(response, '550.00 ₽')

        self.assertTrue(self.product_active.in_stock)
        self.assertFalse(self.product_out_of_stock.in_stock)
