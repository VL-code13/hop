"""
Сервисный слой эмуляции и обработки платежей интернет-магазина Hop & Barley.

Реализует требования разделов 3.4 («Выбор способа оплаты: мок/эмуляция»)
и 4 («Платежи и транзакции») ТЗ.
"""

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from orders.models import Order

from .models import PaymentTransaction


class PaymentError(Exception):
    """Базовое исключение ошибок платежного сервиса."""

    pass


class OrderAlreadyPaidError(PaymentError):
    """Заказ уже был успешно оплачен ранее."""

    pass


class InvalidOrderStateError(PaymentError):
    """Заказ находится в статусе, недоступном для оплаты (например, отменен)."""

    pass


class PaymentService:
    """
    Инкапсулирует бизнес-логику проведения транзакций и взаимодействия с платежным шлюзом.
    """

    @classmethod
    def get_payable_order(cls, order_id: int, user: Any) -> Order:
        """
        Получает заказ пользователя и валидирует его статус перед оплатой.

        Бизнес-правила:
        1. Заказ должен принадлежать текущему пользователю.
        2. Заказ в статусе PAID нельзя оплатить повторно.
        3. Заказ в статусе CANCELLED нельзя оплатить.
        """
        try:
            order = Order.objects.get(id=order_id, user=user)
        except Order.DoesNotExist as err:
            raise ObjectDoesNotExist(f'Заказ #{order_id} не найден.') from err

        if order.status == Order.Status.PAID:
            raise OrderAlreadyPaidError(f'Заказ #{order.id} уже оплачен.')

        if order.status == Order.Status.CANCELLED:
            raise InvalidOrderStateError(f'Заказ #{order.id} отменен и не может быть оплачен.')

        return order

    @classmethod
    @transaction.atomic
    def process_payment(
        cls,
        order: Order,
        payment_method: str = PaymentTransaction.Method.CARD,
        simulate_success: bool = True,
    ) -> PaymentTransaction:
        """
        Эмулирует проведение платежа через внешнюю платежную систему.

        Использует select_for_update() для защиты от состояния гонки
        при повторных кликах пользователя.
        """
        # Блокируем строку заказа от параллельных модификаций
        locked_order = Order.objects.select_for_update().get(id=order.id)

        if locked_order.status == Order.Status.PAID:
            raise OrderAlreadyPaidError(f'Заказ #{locked_order.id} уже оплачен.')

        if locked_order.status == Order.Status.CANCELLED:
            raise InvalidOrderStateError(f'Заказ #{locked_order.id} отменен.')

        # Валидируем метод оплаты по белому списку модели
        valid_methods = [choice[0] for choice in PaymentTransaction.Method.choices]
        if payment_method not in valid_methods:
            payment_method = PaymentTransaction.Method.CARD

        # Определяем статус эмуляции
        tx_status = PaymentTransaction.Status.SUCCESS if simulate_success else PaymentTransaction.Status.FAILED

        # Создаем запись финансовой транзакции
        payment = PaymentTransaction.objects.create(
            order=locked_order,
            amount=locked_order.total_price,
            payment_method=payment_method,
            status=tx_status,
        )

        # При успехе переводим заказ в статус PAID
        if simulate_success:
            locked_order.status = Order.Status.PAID
            # Обновляем метод оплаты в заказе, если покупатель выбрал другой на чекауте
            locked_order.payment_method = payment_method
            locked_order.save(update_fields=['status', 'payment_method', 'updated_at'])

        return payment
