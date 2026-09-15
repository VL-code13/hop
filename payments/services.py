"""Сервисная логика эмуляции оплаты заказа."""

from django.db import transaction
from orders.models import Order
from .models import PaymentTransaction


class PaymentService:
    """Сервис обработки платежей."""

    @staticmethod
    @transaction.atomic
    def process_payment(
        order: Order,
        payment_method: str = 'card',
        simulate_success: bool = True,
    ) -> PaymentTransaction:
        """
        Эмулирует проведение платежа через платежный шлюз.

        При успехе переводит транзакцию в SUCCESS, а заказ в Order.Status.PAID.
        """
        tx_status = (
            PaymentTransaction.Status.SUCCESS
            if simulate_success
            else PaymentTransaction.Status.FAILED
        )

        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_price,
            payment_method=payment_method,
            status=tx_status,
        )

        if simulate_success:
            order.status = Order.Status.PAID
            order.save(update_fields=['status'])

        return payment