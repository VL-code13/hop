"""
Контроллеры Django REST Framework для заказов и корзины.

Реализует требования раздела 3.7 ТЗ (/api/orders/ и /api/cart/)
и документирование схем OpenAPI по разделу 3.8 ТЗ.
"""

from typing import Any
from django.db import transaction
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from .cart import Cart
from .models import Order, OrderItem
from .serializers import (
    CartItemSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)


class CartItemResponseSerializer(serializers.Serializer):
    """Схема элемента корзины для Swagger-документации."""

    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class CartResponseSerializer(serializers.Serializer):
    """Схема ответа корзины для Swagger-документации."""

    items = CartItemResponseSerializer(many=True)
    total_items = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Управление заказами пользователя через REST API (раздел 3.7 ТЗ).

    Доступно только авторизованным пользователям с JWT-токеном.
    Пользователь имеет доступ только к своим собственным заказам,
    что удовлетворяет требованию разграничения прав доступа.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self) -> Any:
        """Возвращает только заказы текущего авторизованного пользователя."""
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related('items__product')
            .order_by('-created_at')
        )

    def get_serializer_class(self) -> Any:
        """Выбирает сериализатор в зависимости от выполняемого действия."""
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Создает заказ из сессионной корзины пользователя с валидацией остатков."""
        cart = Cart(request)
        if len(cart) == 0:
            return Response(
                {'detail': 'Невозможно оформить заказ: корзина пуста.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            for item in cart:
                prod: Product = item['product']
                if prod.stock < item['quantity']:
                    return Response(
                        {'detail': f'Недостаточно товара «{prod.name}» (остаток: {prod.stock}).'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            order = Order.objects.create(
                user=request.user,
                shipping_address=serializer.validated_data.get('shipping_address', ''),
                payment_method=serializer.validated_data.get('payment_method', Order.PaymentMethod.CARD),
                total_price=cart.get_total_price(),
                status=Order.Status.PENDING,
            )

            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    price=item['price'],
                    quantity=item['quantity'],
                )
                prod = item['product']
                prod.stock -= item['quantity']
                prod.save(update_fields=['stock'])

        cart.clear()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Отменяет заказ (переводит в статус CANCELLED), если он ещё не отправлен."""
        order: Order = self.get_object()
        if order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
            return Response(
                {'detail': 'Нельзя отменить заказ, который уже отправлен или доставлен.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status'])
        return Response({'detail': f'Заказ #{order.id} успешно отменен.'})


class CartAPIView(APIView):
    """
    API управления корзиной покупок (раздел 3.7 ТЗ: /api/cart/).

    Поддерживает методы:
    - GET: чтение содержимого корзины;
    - POST: добавление товара в корзину;
    - PATCH: обновление количества товара;
    - DELETE: очистка корзины.
    """

    schema = AutoSchema()

    @extend_schema(
        summary='Получить содержимое корзины',
        description='Возвращает список товаров в корзине, их количество и общую стоимость.',
        responses={200: CartResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        """Возвращает список товаров в корзине и общую стоимость."""
        cart = Cart(request)
        items = [
            {
                'product_id': item['product'].id,
                'product_name': item['product'].name,
                'price': item['price'],
                'quantity': item['quantity'],
                'total_price': item['total_price'],
            }
            for item in cart
        ]
        return Response({
            'items': items,
            'total_items': len(cart),
            'total_price': cart.get_total_price(),
        })

    @extend_schema(
        summary='Добавить товар в корзину',
        request=CartItemSerializer,
        responses={
            200: OpenApiResponse(description='Товар успешно добавлен'),
            400: OpenApiResponse(description='Недостаточно товара на складе'),
        },
    )
    def post(self, request: Request) -> Response:
        """Добавляет товар в корзину через API."""
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']

        product = generics.get_object_or_404(Product, id=product_id, is_active=True)
        cart = Cart(request)

        already_in_cart = cart.cart.get(str(product_id), {}).get('quantity', 0)
        if already_in_cart + quantity > product.stock:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.add(product=product, quantity=quantity, override_quantity=False)
        return Response({'detail': f'Товар «{product.name}» добавлен в корзину.'}, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Обновить количество товара в корзине',
        description='Перезаписывает точное количество для указанного товара (метод PATCH по разделу 3.7 ТЗ).',
        request=CartItemSerializer,
        responses={
            200: OpenApiResponse(description='Количество товара обновлено'),
            400: OpenApiResponse(description='Недостаточно товара на складе'),
        },
    )
    def patch(self, request: Request) -> Response:
        """Перезаписывает точное количество единиц товара в корзине."""
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']

        product = generics.get_object_or_404(Product, id=product_id, is_active=True)
        cart = Cart(request)

        if quantity > product.stock:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.add(product=product, quantity=quantity, override_quantity=True)
        return Response({'detail': f'Количество для «{product.name}» обновлено.'}, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Очистить корзину',
        responses={204: OpenApiResponse(description='Корзина успешно очищена')},
    )
    def delete(self, request: Request) -> Response:
        """Полностью очищает корзину."""
        cart = Cart(request)
        cart.clear()
        return Response({'detail': 'Корзина успешно очищена.'}, status=status.HTTP_204_NO_CONTENT)
