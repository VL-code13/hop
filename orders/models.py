"""
Модели базы данных для оформления заказов и сохранения товарных чеков.

Реализует требования разделов 3.4 («Оформление заказа») и 4 («Структура данных») ТЗ.
"""

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F
from django.utils import timezone

from products.models import Product


class Order(models.Model):
    """Модель заказа покупателя.

    Хранит статус жизненного цикла, метод оплаты, итоговую стоимость
    и снимок контактных данных доставки (раздел 4 ТЗ).
    """

    class Status(models.TextChoices):
        """Статусы жизненного цикла заказа."""

        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        SHIPPED = 'shipped', 'Отправлен'
        DELIVERED = 'delivered', 'Доставлен'
        CANCELLED = 'cancelled', 'Отменен'

    class PaymentMethod(models.TextChoices):
        """Методы оплаты покупки (раздел 3.4 ТЗ)."""

        CARD = 'card', 'Банковской картой онлайн'
        WALLET = 'wallet', 'Электронный кошелек / СБП'
        CASH = 'cash', 'При получении'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='Покупатель',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус заказа',
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CARD,
        verbose_name='Способ оплаты',
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Итоговая сумма',
    )
    shipping_address = models.TextField(
        blank=True,
        null=True,
        verbose_name='Адрес доставки и контакты',
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
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self) -> str:
        """Строковое представление заказа."""
        return f'Заказ #{self.pk} ({self.user.username})'

    def get_total_cost(self) -> Decimal:
        """Рассчитывает суммарную стоимость всех связанных товарных позиций."""
        return sum(
            (item.get_cost() for item in self.items.all()),
            Decimal('0.00'),
        )

    def recalculate_total(self, *, save: bool = True) -> Decimal:
        """Пересчитывает ``total_price`` по текущим позициям.

        Используется в админке (``OrderAdmin.save_formset``) и в
        ``OrderItem.delete()`` для синхронизации snapshot-суммы заказа
        после ручного редактирования позиций.

        Args:
            save: Если True — сохраняет новое значение в БД.

        Returns:
            Decimal: Актуальная сумма по позициям.
        """
        # Сбрасываем кеш prefetch, если он был заполнен до удаления позиции.
        if hasattr(self, '_prefetched_objects_cache'):
            self._prefetched_objects_cache.pop('items', None)

        total = self.get_total_cost()
        if save and total != self.total_price:
            self.total_price = total
            self.save(update_fields=['total_price', 'updated_at'])
        return total


class OrderItem(models.Model):
    """Товарная позиция в чеке заказа.

    Фиксирует цену товара на момент покупки (price snapshot) по разделу 4 ТЗ.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заказ',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Количество',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена фиксации',
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self) -> str:
        """Строковое представление позиции."""
        return f'{self.product.name} (x{self.quantity})'

    def get_cost(self) -> Decimal:
        """Вычисляет общую стоимость позиции."""
        return self.price * self.quantity

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Сохраняет позицию, автозаполняя цену для новых записей.

        Поле ``price`` — snapshot цены на момент покупки. В админке оно
        объявлено как ``readonly_fields``, чтобы нельзя было менять цену
        задним числом у существующих позиций. Побочный эффект: при создании
        **новой** позиции через админку форма не передаёт ``price``,
        значение остаётся ``None`` и падает ``IntegrityError:
        NOT NULL constraint failed: orders_orderitem.price``.

        Метод подставляет текущую ``Product.price``, если ``price``
        не задан. Для существующих позиций ничего не меняется — ``price``
        уже зафиксирован при оформлении заказа через
        ``OrderCreateSerializer``.
        """
        if self.price is None and self.product_id:
            self.price = self.product.price
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Удаляет позицию, возвращая остаток товара на склад.

        Логика возврата зависит от статуса заказа:

        - ``PENDING`` / ``PAID`` / ``SHIPPED`` — товар ещё не у покупателя,
          остаток возвращается на склад атомарным ``F('stock') + quantity``.
        - ``DELIVERED`` — товар уже доставлен, остаток **не** возвращается.
        - ``CANCELLED`` — остаток уже возвращён при отмене всего заказа
          через ``OrderCancelSerializer``, повторный возврат запрещён.

        После удаления позиции ``Order.total_price`` пересчитывается
        по оставшимся позициям, чтобы snapshot-сумма оставалась
        актуальной.

        Returns:
            tuple[int, dict[str, int]]: Результат ``super().delete()`` —
            число удалённых объектов и разбивка по моделям.
        """
        order = self.order
        product_id = self.product_id
        quantity = self.quantity

        # Возвращаем остаток, только если заказ не доставлен и не отменён.
        should_restock = order.status not in (
            Order.Status.DELIVERED,
            Order.Status.CANCELLED,
        )

        if should_restock and product_id:
            Product.objects.filter(id=product_id).update(
                stock=F('stock') + quantity,
                updated_at=timezone.now(),
            )

        result = super().delete(*args, **kwargs)

        # Пересчитываем итоговую сумму заказа, если он ещё существует.
        if order.pk:
            order.recalculate_total()

        return result
