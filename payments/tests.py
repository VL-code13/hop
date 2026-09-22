"""
Модульные тесты приложения оплаты.

Реализует требования разделов 3.4 и 6.3 ТЗ:
- Эмуляция успешного платежа;
- Перевод заказа в статус PAID;
- Защита от повторной оплаты оплаченного заказа;
- Защита от оплаты отмененного заказа;
- Защита от двойной оплаты на уровне БД (UniqueConstraint);
- Защита от IDOR (попытка оплатить чужой заказ);
- Проверка, что неуспешная оплата не меняет статус заказа.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase

from orders.models import Order
from payments.models import PaymentTransaction
from payments.services import (
    InvalidOrderStateError,
    OrderAlreadyPaidError,
    OrderNotFoundError,
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

    # ── Существующие тесты ────────────────────────────────────────

    def test_successful_payment_updates_order_status(self) -> None:
        """Успешная оплата переводит статус заказа в PAID."""
        tx = PaymentService.process_payment(
            order=self.order,
            user=self.user,
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

    # ── Новые тесты ───────────────────────────────────────────────

    def test_unique_constraint_blocks_double_success(self) -> None:
        """БД-инвариант: вторая SUCCESS-транзакция на заказ не создаётся.

        Проверяет `UniqueConstraint(condition=Q(status=SUCCESS))` на модели.
        """
        PaymentTransaction.objects.create(
            order=self.order,
            amount=self.order.total_price,
            status=PaymentTransaction.Status.SUCCESS,
        )

        with self.assertRaises(IntegrityError):
            PaymentTransaction.objects.create(
                order=self.order,
                amount=self.order.total_price,
                status=PaymentTransaction.Status.SUCCESS,
            )

    def test_failed_payment_does_not_change_order_status(self) -> None:
        """Эмуляция отказа не переводит заказ в PAID и не создаёт SUCCESS."""
        tx = PaymentService.process_payment(
            order=self.order,
            user=self.user,
            payment_method='card',
            simulate_success=False,
        )

        self.order.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_user_cannot_pay_other_user_order(self) -> None:
        """IDOR-защита: чужой пользователь не может оплатить заказ."""
        other_user = User.objects.create_user(
            username='intruder',
            email='intruder@hopbarley.ru',
            password='Password123!',
        )

        with self.assertRaises(OrderNotFoundError):
            PaymentService.process_payment(
                order=self.order,
                user=other_user,
                payment_method='card',
                simulate_success=True,
            )
