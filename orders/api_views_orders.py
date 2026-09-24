"""
Контроллеры Django REST Framework для заказов и корзины.

Реализует требования раздела 3.7 ТЗ:
- /api/orders/  — CRUD заказов пользователя (JWT-авторизация).
- /api/cart/    — управление сессионной корзиной через API.
"""

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .cart import Cart
from .models import Order
from .serializers import (
    CartItemSerializer,
    CartResponseSerializer,
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Управление заказами пользователя через REST API (раздел 3.7 ТЗ).

    Контроллер полностью облегчен: создание и отмена заказов вынесены в сериализаторы.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self) -> Any:
        """
        Возвращает заказы текущего пользователя с предварительной загрузкой связанных позиций.
        """
        user: Any = self.request.user
        return Order.objects.filter(user=user).prefetch_related('items__product').order_by('-created_at')

    def get_serializer_class(self) -> Any:
        """Разделение сериализаторов в зависимости от действия."""
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    @extend_schema(
        summary='Создать заказ',
        description='Оформляет заказ на основе товаров из сессионной корзины пользователя.',
        responses={201: OrderSerializer, 400: OpenApiResponse(description='Ошибка валидации остатков или данных')},
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Оформление заказа через OrderCreateSerializer."""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='Отменить заказ',
        description='Переводит статус заказа в CANCELLED и возвращает списанный товар обратно на склад.',
        responses={
            204: OpenApiResponse(description='Заказ успешно отменен'),
            400: OpenApiResponse(description='Заказ нельзя отменить'),
        },
    )
    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Отмена заказа через специализированный OrderCancelSerializer."""
        order = self.get_object()
        cancel_serializer = OrderCancelSerializer(data={}, context={'order': order})
        cancel_serializer.is_valid(raise_exception=True)
        cancel_serializer.cancel()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartAPIView(APIView):
    """
    API управления сессионной корзиной пользователя (раздел 3.7 ТЗ).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Получить состав корзины', responses={200: CartResponseSerializer})
    def get(self, request: Request) -> Response:
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
        return Response(
            {
                'items': items,
                'total_items': len(cart),
                'total_price': cart.get_total_price(),
            }
        )

    @extend_schema(
        summary='Добавить товар в корзину',
        request=CartItemSerializer,
        responses={
            200: OpenApiResponse(description='Товар добавлен'),
            400: OpenApiResponse(description='Превышен остаток'),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        cart = Cart(request)
        success = cart.add(product=product, quantity=quantity, override_quantity=False)
        if not success:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'detail': f'Товар «{product.name}» добавлен в корзину.'}, status=status.HTTP_200_OK)

    @extend_schema(summary='Обновить количество товара в корзине', request=CartItemSerializer)
    def patch(self, request: Request) -> Response:
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        cart = Cart(request)
        success = cart.add(product=product, quantity=quantity, override_quantity=True)
        if not success:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'detail': f'Количество для «{product.name}» обновлено.'}, status=status.HTTP_200_OK)

    @extend_schema(summary='Очистить корзину')
    def delete(self, request: Request) -> Response:
        cart = Cart(request)
        cart.clear()
        return Response({'detail': 'Корзина очищена.'}, status=status.HTTP_200_OK)
