"""
Сериализаторы Django REST Framework для корзины и заказов.

Реализует требования раздела 3.7 ТЗ (/api/orders/ и /api/cart/).
"""

from typing import Sequence
from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор товарной позиции внутри чека заказа."""

    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = OrderItem
        fields: Sequence[str] = ('id', 'product', 'product_name', 'price', 'quantity')
        read_only_fields: Sequence[str] = ('price',)


class OrderSerializer(serializers.ModelSerializer):
    """Сериализатор заказа с вложенными позициями товаров."""

    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Order
        fields: Sequence[str] = (
            'id',
            'user',
            'status',
            'payment_method',
            'total_price',
            'shipping_address',
            'created_at',
            'items',
        )
        read_only_fields: Sequence[str] = ('total_price', 'created_at', 'status')


class OrderCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания заказа через API на основе сессионной корзины."""

    class Meta:
        model = Order
        fields: Sequence[str] = ('shipping_address', 'payment_method')


class CartItemSerializer(serializers.Serializer):
    """Сериализатор отдельной позиции корзины в API."""

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
