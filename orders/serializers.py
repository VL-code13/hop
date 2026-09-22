"""
Сериализаторы Django REST Framework для корзины и заказов.

Реализует требования разделов 3.4, 3.7 и 3.8 ТЗ:
- Инкапсуляция бизнес-логики оформления заказа (списание остатков, snapshot цен, транзакции, email).
- Инкапсуляция бизнес-логики отмены заказа (возврат товаров на склад в транзакции).
- Сериализация сессионной корзины для API и схемы OpenAPI/Swagger.
"""

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.mail import mail_admins, send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from products.models import Product

from .cart import Cart
from .models import Order, OrderItem

logger = logging.getLogger(__name__)


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Сериализатор товарной позиции внутри чека заказа.
    Используется для вложенного отображения в деталях заказа.
    """

    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'price', 'quantity')
        read_only_fields = ('id', 'product', 'product_name', 'price', 'quantity')


class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор для чтения данных о заказе (GET list / GET retrieve).
    Включает в себя вложенный список купленных позиций и строковый статус.
    """

    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Order
        fields = (
            'id',
            'user',
            'status',
            'payment_method',
            'total_price',
            'shipping_address',
            'created_at',
            'items',
        )
        read_only_fields = ('id', 'user', 'status', 'total_price', 'created_at', 'items')


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Сериализатор оформления заказа.

    Инкапсулирует в себе всю ключевую бизнес-логику магазина:
    1. Комплексная валидация корзины и доступных складских остатков.
    2. Атомарное сохранение заказа с блокировкой строк (``select_for_update``)
       и атомарным списанием через ``F('stock') - qty`` во избежание race conditions.
    3. Фиксация цен на момент покупки (price snapshot).
    4. Списание физических остатков товаров со склада.
    5. Очистка сессионной корзины.
    6. Отправка email-уведомлений покупателю и администраторам (раздел 3.4 ТЗ).
    """

    payment_method = serializers.ChoiceField(
        choices=Order.PaymentMethod.choices,
        default=Order.PaymentMethod.CARD,
        required=False,
    )

    class Meta:
        model = Order
        fields = ('shipping_address', 'payment_method')

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Проверяет наличие товаров в сессии и фактический остаток на складе.
        """
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Отсутствует контекст HTTP-запроса.')

        # Извлекаем сессионную корзину
        cart = Cart(request)
        if len(cart) == 0:
            raise serializers.ValidationError('Невозможно оформить заказ: корзина пуста.')

        # Предварительная проверка остатков до открытия тяжелой транзакции БД
        for item in cart:
            product: Product = item['product']
            quantity: int = item['quantity']
            if product.stock < quantity:
                raise serializers.ValidationError(
                    f'Недостаточно товара «{product.name}» на складе. '
                    f'В наличии: {product.stock} шт., запрошено: {quantity} шт.'
                )

        # Передаем корзину в validated_data для использования в create()
        attrs['cart'] = cart
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Order:
        """
        Создает заказ, позиции чека, списывает остатки и отправляет уведомления.

        Списание остатков выполняется атомарно на уровне БД через
        ``Product.objects.filter(stock__gte=qty).update(stock=F('stock') - qty)``.
        Это исключает overselling даже там, где ``select_for_update()``
        не работает как реальная блокировка (например, на SQLite).
        """
        cart: Cart = validated_data.pop('cart')
        user = self.context['request'].user
        total_price: Decimal = cart.get_total_price()

        with transaction.atomic():
            # 1. Блокируем строки покупаемых товаров (реальная блокировка на PostgreSQL)
            product_ids = [item['product'].id for item in cart]
            locked_products = {p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)}

            # 2. Повторная проверка остатков под блокировкой
            for item in cart:
                p = locked_products.get(item['product'].id)
                if not p or p.stock < item['quantity']:
                    raise serializers.ValidationError(
                        f'Остаток товара «{item["product"].name}» изменился. Повторите попытку.'
                    )

            # 3. Создаём заголовок заказа
            order = Order.objects.create(
                user=user,
                shipping_address=validated_data.get('shipping_address', ''),
                payment_method=validated_data.get('payment_method', Order.PaymentMethod.CARD),
                total_price=total_price,
                status=Order.Status.PENDING,
            )

            # 4. Создаём позиции заказа и списываем остатки атомарно.
            #    filter(stock__gte=...) + update(F(...)) — один UPDATE-запрос,
            #    в котором проверка остатка и его уменьшение происходят вместе.
            #    updated_at задаём вручную: auto_now не срабатывает через .update().
            for item in cart:
                p = locked_products[item['product'].id]
                OrderItem.objects.create(
                    order=order,
                    product=p,
                    price=item['price'],  # снимок цены на момент покупки
                    quantity=item['quantity'],
                )
                updated = Product.objects.filter(
                    id=p.id,
                    stock__gte=item['quantity'],
                ).update(
                    stock=F('stock') - item['quantity'],
                    updated_at=timezone.now(),
                )
                if not updated:
                    raise serializers.ValidationError(f'Остаток товара «{p.name}» изменился. Повторите попытку.')

        # 5. Очищаем корзину после успешной транзакции
        cart.clear()

        # 6. Отправляем email-уведомления (раздел 3.4 ТЗ)
        self._send_order_notifications(order, user)

        return order

    def _send_order_notifications(self, order: Order, user: Any) -> None:
        """
        Безопасная отправка транзакционных писем покупателю и администраторам.

        Сбой SMTP не должен откатывать уже созданный заказ, но обязан
        попасть в лог — иначе о проблеме с почтой никто не узнает.
        """
        try:
            send_mail(
                subject=f'Hop & Barley: Заказ #{order.id} принят в обработку',
                message=(
                    f'Здравствуйте, {user.get_full_name() or user.username}!\n\n'
                    f'Ваш заказ #{order.id} на сумму {order.total_price} ₽ успешно создан.\n'
                    f'Способ оплаты: {order.get_payment_method_display()}.\n'
                    f'Адрес доставки: {order.shipping_address}\n\n'
                    'Спасибо, что выбрали Hop & Barley!'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            mail_admins(
                subject=f'Новый заказ #{order.id} на сумму {order.total_price} ₽',
                message=f'Пользователь {user.username} оформил заказ #{order.id}.',
                fail_silently=True,
            )
        except Exception:
            logger.exception(
                'Не удалось отправить email-уведомления по заказу #%s',
                order.id,
            )


class OrderCancelSerializer(serializers.Serializer):
    """
    Сериализатор отмены заказа.
    Проверяет статус и возвращает списанные товары на склад в транзакции.
    """

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        order: Order = self.context['order']
        if order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
            raise serializers.ValidationError('Нельзя отменить заказ, который уже отправлен или доставлен.')
        if order.status == Order.Status.CANCELLED:
            raise serializers.ValidationError('Заказ уже отменен.')
        return attrs

    def cancel(self) -> Order:
        """Атомарно возвращает остатки на склад и переводит заказ в CANCELLED.

        Возврат выполняется атомарным ``F('stock') + qty`` — это исключает
        lost update, если параллельно тот же товар покупает другой клиент.
        """
        order: Order = self.context['order']
        with transaction.atomic():
            for item in order.items.select_related('product'):
                Product.objects.filter(id=item.product_id).update(
                    stock=F('stock') + item.quantity,
                    updated_at=timezone.now(),
                )

            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])
        return order


class CartItemSerializer(serializers.Serializer):
    """
    Сериализатор входных параметров для добавления/изменения количества товара в корзине.
    Автоматически валидирует существование и активность товара по ID.
    """

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        source='product',
    )
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)


class CartItemResponseSerializer(serializers.Serializer):
    """Схема одной товарной позиции корзины для OpenAPI / Swagger (раздел 3.8 ТЗ)."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class CartResponseSerializer(serializers.Serializer):
    """Схема итогового ответа корзины со сводной информацией для API документации."""

    items = CartItemResponseSerializer(many=True)
    total_items = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
