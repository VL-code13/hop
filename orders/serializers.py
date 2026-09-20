"""
Сериализаторы Django REST Framework для корзины и заказов.

Реализует требования раздела 3.7 ТЗ (/api/orders/ и /api/cart/).
"""

from rest_framework import serializers

from products.models import Product

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор товарной позиции внутри чека заказа."""

    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'price', 'quantity')
        read_only_fields = ('price', 'product', 'quantity')


class OrderSerializer(serializers.ModelSerializer):
    """Сериализатор заказа с вложенными позициями товаров."""

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
        read_only_fields = ('total_price', 'created_at', 'status')


class OrderCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания заказа через API на основе сессионной корзины."""

    class Meta:
        model = Order
        fields = ('shipping_address', 'payment_method')


class CartItemSerializer(serializers.Serializer):
    """
    Сериализатор входных данных для добавления/обновления позиции корзины.

    product_id валидируется через PrimaryKeyRelatedField: DRF сам вернёт
    404 на несуществующий или скрытый (is_active=False) товар — ручной
    get_object_or_404 в представлении не нужен.
    """

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        source='product',
    )
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)


class CartItemResponseSerializer(serializers.Serializer):
    """Схема элемента корзины для ответа API и Swagger-документации."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class CartResponseSerializer(serializers.Serializer):
    """Схема ответа корзины для API и Swagger-документации."""

    items = CartItemResponseSerializer(many=True)
    total_items = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
