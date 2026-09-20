"""Модульные тесты приложения оплаты."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order
from payments.models import PaymentTransaction
from payments.services import PaymentService

User = get_user_model()


class PaymentServiceTestCase(TestCase):
    """Тестирование бизнес-логики сервиса оплаты."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='buyer',
            email='buyer@hopbarley.ru',
            password='Password123!',
        )
        self.order = Order.objects.create(
            user=self.user,
            total_price=Decimal('1200.00'),
            shipping_address='г. Москва, ул. Ленина, 1',
            status=Order.Status.PENDING,
        )

    def test_successful_payment_updates_order_status(self) -> None:
        """Успешная оплата переводит статус заказа в PAID."""
        tx = PaymentService.process_payment(
            order=self.order,
            payment_method='card',
            simulate_success=True,
        )

        self.order.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.payments.count(), 1)
