"""
Модульные тесты приложения orders.

Реализует требования разделов 6.3 («Тестирование: корзина, заказ, бизнес-правила») и 8 ТЗ.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from products.models import Category, Product

from .models import Order, OrderItem

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
        # При превышении остатка корзина не пополняется
        self.assertEqual(cart.get(str(self.product.id), {}).get('quantity', 0), 0)

    def test_checkout_creates_order_and_deducts_stock(self) -> None:
        """
        Успешное оформление заказа:
        1. Создает запись Order и OrderItem;
        2. Списывает остаток товара на складе;
        3. Очищает сессионную корзину;
        4. Делает редирект на success.
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
            'shipping_address': 'Лиговский проспект, д. 50',
            'payment_method': Order.PaymentMethod.CARD,
        }
        response = self.client.post(reverse('orders:checkout'), data=checkout_data)
        self.assertEqual(response.status_code, 302)

        # Проверяем уменьшение остатка
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

        # Проверяем создание заказа в базе
        order = Order.objects.filter(user=self.user).first()
        self.assertIsNotNone(order)
        assert order is not None
        self.assertEqual(order.total_price, Decimal('1860.00'))

        # Проверяем очистку корзины
        session_cart = self.client.session.get('cart', {})
        self.assertEqual(len(session_cart), 0)


class OrderItemDeleteTestCase(TestCase):
    """Тесты возврата остатка при удалении позиции заказа.

    Для доступа к позиции используется ``order.items.get(product=...)``,
    а не ``order.items.first()``. Разница: ``get()`` возвращает сразу
    ``OrderItem`` и падает с ``DoesNotExist``, если объекта нет — mypy
    доволен. ``first()`` возвращает ``OrderItem | None`` и требует
    дополнительной проверки на ``None``.
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='deleter',
            email='deleter@example.com',
            password='pass12345',
        )
        self.category = Category.objects.create(name='Хмель', slug='hops')
        self.product = Product.objects.create(
            name='Citra',
            slug='citra',
            price=Decimal('500.00'),
            category=self.category,
            stock=10,
            is_active=True,
        )

    def _make_order(self, status: str) -> Order:
        """Создаёт заказ с одной позицией (товар x3) и заданным статусом."""
        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('1500.00'),
            status=status,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('500.00'),
            quantity=3,
        )
        return order

    def test_delete_item_returns_stock_for_pending(self) -> None:
        """PENDING: удаление позиции возвращает остаток на склад."""
        order = self._make_order(Order.Status.PENDING)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 13)  # 10 + 3

    def test_delete_item_returns_stock_for_paid(self) -> None:
        """PAID: удаление позиции возвращает остаток."""
        order = self._make_order(Order.Status.PAID)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 13)

    def test_delete_item_does_not_return_stock_for_delivered(self) -> None:
        """DELIVERED: остаток НЕ возвращается — товар у покупателя."""
        order = self._make_order(Order.Status.DELIVERED)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_delete_item_does_not_return_stock_for_cancelled(self) -> None:
        """CANCELLED: остаток уже возвращён при отмене заказа, повторно нельзя."""
        order = self._make_order(Order.Status.CANCELLED)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_delete_item_recalculates_total(self) -> None:
        """Удаление позиции пересчитывает Order.total_price."""
        order = self._make_order(Order.Status.PENDING)
        order.items.get(product=self.product).delete()
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('0.00'))
