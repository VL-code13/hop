"""Сервисный слой эмуляции и обработки платежей интернет-магазина Hop & Barley.

Реализует требования разделов 3.4 («Выбор способа оплаты: мок/эмуляция»)
и 4 («Платежи и транзакции») ТЗ.
"""

import logging
from typing import Any

from django.db import IntegrityError, transaction

from orders.models import Order

from .models import PaymentTransaction

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Базовое исключение ошибок платежного сервиса."""


class OrderNotFoundError(PaymentError):
    """Заказ не найден или не принадлежит пользователю."""


class OrderAlreadyPaidError(PaymentError):
    """Заказ уже был успешно оплачен ранее."""


class InvalidOrderStateError(PaymentError):
    """Заказ находится в статусе, недоступном для оплаты (например, отменен)."""


class PaymentService:
    """Инкапсулирует бизнес-логику проведения транзакций и работы со шлюзом."""

    @classmethod
    def get_payable_order(cls, order_id: int, user: Any) -> Order:
        """Получает заказ пользователя и валидирует его статус перед оплатой.

        Бизнес-правила:
        1. Заказ должен принадлежать текущему пользователю.
        2. Заказ в статусе PAID нельзя оплатить повторно.
        3. Заказ в статусе CANCELLED нельзя оплатить.

        Args:
            order_id: ID заказа.
            user: Пользователь, запрашивающий оплату.

        Returns:
            Order: Заказ, готовый к оплате.

        Raises:
            OrderNotFoundError: Заказ не найден или принадлежит другому пользователю.
            OrderAlreadyPaidError: Заказ уже оплачен.
            InvalidOrderStateError: Заказ отменён.
        """
        try:
            order = Order.objects.get(id=order_id, user=user)
        except Order.DoesNotExist as err:
            raise OrderNotFoundError(f'Заказ #{order_id} не найден.') from err

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
        user: Any,
        payment_method: str = PaymentTransaction.Method.CARD,
        simulate_success: bool = True,
    ) -> PaymentTransaction:
        """Эмулирует проведение платежа через внешнюю платежную систему.

        Транзакция атомарна: либо создаётся платёж и обновляется заказ,
        либо откатывается всё. Строка заказа блокируется
        ``select_for_update()`` для защиты от race condition.

        Двойная оплата защищена на двух уровнях:
        1. Проверка статуса внутри транзакции (сервисный уровень).
        2. ``UniqueConstraint`` с условием ``status=SUCCESS`` на уровне БД
           (страховка, если кто-то обошёл сервис).

        Args:
            order: Заказ, который оплачивается (уже проверен на владельца).
            user: Пользователь — проверяется повторно в фильтре
                ``select_for_update`` для защиты от IDOR.
            payment_method: Метод оплаты. Невалидный откатывается к CARD.
            simulate_success: True — эмуляция успеха; False — эмуляция отказа.

        Returns:
            PaymentTransaction: Созданная транзакция.

        Raises:
            OrderNotFoundError: Заказ не найден или не принадлежит user.
            OrderAlreadyPaidError: Заказ уже оплачен (проверка или IntegrityError).
            InvalidOrderStateError: Заказ отменён.
        """
        # Блокируем строку заказа; фильтр по user закрывает IDOR архитектурно
        try:
            locked_order = Order.objects.select_for_update().get(id=order.id, user=user)
        except Order.DoesNotExist as err:
            raise OrderNotFoundError(f'Заказ #{order.id} не найден.') from err

        if locked_order.status == Order.Status.PAID:
            raise OrderAlreadyPaidError(f'Заказ #{locked_order.id} уже оплачен.')

        if locked_order.status == Order.Status.CANCELLED:
            raise InvalidOrderStateError(f'Заказ #{locked_order.id} отменен.')

        # Валидация метода оплаты по белому списку
        valid_methods = {choice[0] for choice in PaymentTransaction.Method.choices}
        if payment_method not in valid_methods:
            payment_method = PaymentTransaction.Method.CARD

        tx_status = PaymentTransaction.Status.SUCCESS if simulate_success else PaymentTransaction.Status.FAILED

        try:
            payment = PaymentTransaction.objects.create(
                order=locked_order,
                amount=locked_order.total_price,
                payment_method=payment_method,
                status=tx_status,
            )
        except IntegrityError as err:
            # Сработал UniqueConstraint(condition=Q(status=SUCCESS)).
            # Значит, параллельная транзакция уже оплатила этот заказ.
            logger.warning(
                'Двойная оплата заказа #%s: сработал unique_success_payment_per_order.',
                locked_order.id,
            )
            raise OrderAlreadyPaidError(f'Заказ #{locked_order.id} уже оплачен.') from err

        if simulate_success:
            locked_order.status = Order.Status.PAID
            locked_order.payment_method = payment_method
            locked_order.save(update_fields=['status', 'payment_method', 'updated_at'])

        return payment
