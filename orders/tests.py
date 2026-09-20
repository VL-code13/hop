from django.test import TestCase

# Create your tests here.
"""
Модульные тесты приложения orders.

Реализует требования разделов 6.3 («Тестирование: корзина, заказ, бизнес-правила») и 8 ТЗ.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from products.models import Category, Product

from .models import Order

User = get_user_model()


class OrdersBusinessLogicTestCase(TestCase):
    """Тестирование корзины, складских лимитов и процесса чекаута."""

    def setUp(self) -> None:
        """Инициализация тестовых сущностей перед запуском каждого теста."""
        self.user = User.objects.create_user(
            username='brewmaster@example.com',
            email='brewmaster@example.com',
            password='strong_password_123',
        )
        self.category = Category.objects.create(name='Хмель', slug='hops')
        self.product = Product.objects.create(
            name='Centennial Hops',
            slug='centennial-hops',
            price=Decimal('620.00'),
            category=self.category,
            stock=5,
            is_active=True,
        )

    def test_cart_add_valid_quantity(self) -> None:
        """Добавление допустимого количества товара в корзину."""
        response = self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 2},
        )
        self.assertEqual(response.status_code, 302)
        cart = self.client.session['cart']
        self.assertIn(str(self.product.id), cart)
        self.assertEqual(cart[str(self.product.id)]['quantity'], 2)

    def test_cannot_add_more_than_available_stock(self) -> None:
        """
        Бизнес-правило (раздел 6.3 ТЗ):
        Нельзя положить в корзину больше единиц, чем доступно на складе.
        """
        response = self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 10},
        )
        self.assertEqual(response.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertEqual(cart.get(str(self.product.id), {}).get('quantity', 0), 0)

    def test_checkout_creates_order_and_deducts_stock(self) -> None:
        """
        Успешное оформление заказа:
        1. Создает запись Order и OrderItem;
        2. Списывает остаток товара на складе;
        3. Очищает сессионную корзину.
        """
        self.client.login(username='brewmaster@example.com', password='strong_password_123')

        # Добавляем 3 единицы в корзину
        self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 3},
        )

        checkout_data = {
            'full_name': 'Иван Пивоваров',
            'phone': '+7 (999) 111-22-33',
            'city': 'Санкт-Петербург',
            'shipping_address': 'Лиговский проспект, д. 50',
            'payment_method': Order.PaymentMethod.CARD,
        }
        response = self.client.post(reverse('orders:checkout'), data=checkout_data)
        self.assertEqual(response.status_code, 200)

        # Проверяем уменьшение остатка
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

        # Проверяем создание заказа в базе
        order = Order.objects.filter(user=self.user).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.total_price, Decimal('1860.00'))

        # Проверяем очистку корзины
        session_cart = self.client.session.get('cart', {})
        self.assertEqual(len(session_cart), 0)
