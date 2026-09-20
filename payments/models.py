"""Модели платежей и транзакций интернет-магазина."""

import uuid

from django.db import models

from orders.models import Order


class PaymentTransaction(models.Model):
    """Транзакция оплаты заказа."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Ожидает оплаты'
        SUCCESS = 'SUCCESS', 'Успешно оплачено'
        FAILED = 'FAILED', 'Ошибка оплаты'

    class Method(models.TextChoices):
        CARD = 'card', 'Банковская карта'
        WALLET = 'wallet', 'СБП / Электронный кошелек'
        CASH = 'cash', 'Оплата при получении'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID транзакции',
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Заказ',
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма платежа',
    )
    payment_method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CARD,
        verbose_name='Метод оплаты',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус платежа',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления',
    )

    class Meta:
        verbose_name = 'Платежная транзакция'
        verbose_name_plural = 'Платежные транзакции'
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f'Транзакция {self.id} для заказа #{self.order_id} ({self.get_status_display()})'
