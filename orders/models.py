"""Модели базы данных для оформления заказов и сохранения позиций."""

from decimal import Decimal
from django.conf import settings
from django.db import models
from products.models import Product


class Order(models.Model):
    """
    Модель заказа покупателя.

    Хранит статус, итоговую сумму, способ оплаты и адрес доставки.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        SHIPPED = 'shipped', 'Отправлен'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменен'

    class PaymentMethod(models.TextChoices):
        CARD = 'card', 'Банковской картой онлайн'
        CASH = 'cash', 'При получении'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name="Покупатель",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Статус заказа",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CARD,
        verbose_name="Способ оплаты",
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Итоговая сумма",
    )
    shipping_address = models.TextField(
        blank=True,
        null=True,
        verbose_name="Адрес доставки",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self) -> str:
        """Возвращает строковый идентификатор заказа."""
        return f"Заказ #{self.pk} ({self.user.username})"

    def get_total_cost(self) -> Decimal:
        """Рассчитывает суммарную стоимость всех связанных позиций."""
        return sum(
            (item.get_cost() for item in self.items.all()),
            Decimal('0.00'),
        )


class OrderItem(models.Model):
    """
    Позиция товара в конкретном заказе.

    Сохраняет снимок цены (snapshot) на момент оформления покупки.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Заказ",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name="Товар",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="Количество",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена фиксации",
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self) -> str:
        """Возвращает наименование позиции."""
        return f"{self.product.name} (x{self.quantity})"

    def get_cost(self) -> Decimal:
        """Вычисляет общую стоимость позиции."""
        return self.price * self.quantity
