"""
Модульные тесты приложения оплаты.

Реализует требования разделов 3.4 и 6.3 ТЗ:
- Эмуляция успешного платежа;
- Перевод заказа в статус PAID;
- Защита от повторной оплаты оплаченного заказа;
- Защита от оплаты отмененного заказа.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order
from payments.models import PaymentTransaction
from payments.services import (
    InvalidOrderStateError,
    OrderAlreadyPaidError,
    PaymentService,
)

User = get_user_model()


class PaymentServiceTestCase(TestCase):
    """Тестирование бизнес-правил сервиса оплаты."""

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

    def test_cannot_pay_already_paid_order(self) -> None:
        """Повторная попытка оплаты оплаченного заказа вызывает OrderAlreadyPaidError."""
        self.order.status = Order.Status.PAID
        self.order.save()

        with self.assertRaises(OrderAlreadyPaidError):
            PaymentService.get_payable_order(order_id=self.order.id, user=self.user)

    def test_cannot_pay_cancelled_order(self) -> None:
        """Попытка оплаты отмененного заказа вызывает InvalidOrderStateError."""
        self.order.status = Order.Status.CANCELLED
        self.order.save()

        with self.assertRaises(InvalidOrderStateError):
            PaymentService.get_payable_order(order_id=self.order.id, user=self.user)
