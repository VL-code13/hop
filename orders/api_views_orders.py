"""
Контроллеры Django REST Framework для заказов и корзины.

Реализует требования раздела 3.7 ТЗ (/api/orders/ и /api/cart/)
и документирование схем OpenAPI по разделу 3.8 ТЗ.
"""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .cart import Cart
from .models import Order, OrderItem
from .serializers import (
    CartItemSerializer,
    CartResponseSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Управление заказами пользователя через REST API (раздел 3.7 ТЗ).

    Доступно только авторизованным пользователям с JWT-токеном.
    Пользователь имеет доступ только к своим собственным заказам,
    что удовлетворяет требованию разграничения прав доступа.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        """Возвращает только заказы текущего авторизованного пользователя."""
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related('items__product')
            .order_by('-created_at')
        )

    def get_serializer_class(self):
        """Выбирает сериализатор в зависимости от выполняемого действия."""
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request: Request) -> Response:
        """Создаёт заказ из сессионной корзины пользователя с валидацией остатков."""
        cart = Cart(request)
        if len(cart) == 0:
            return Response(
                {'detail': 'Невозможно оформить заказ: корзина пуста.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Проверка остатков ДО транзакции — чтобы не откатывать atomic впустую
        for item in cart:
            if item['product'].stock < item['quantity']:
                return Response(
                    {'detail': f'Недостаточно товара «{item["product"].name}» '
                               f'(остаток: {item["product"].stock}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                shipping_address=serializer.validated_data['shipping_address'],
                payment_method=serializer.validated_data.get(
                    'payment_method', Order.PaymentMethod.CARD
                ),
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
                item['product'].stock -= item['quantity']
                item['product'].save(update_fields=['stock'])

        cart.clear()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def destroy(self, request: Request) -> Response:
        """Отменяет заказ (переводит в CANCELLED), если он ещё не отправлен."""
        order = self.get_object()
        if order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
            return Response(
                {'detail': 'Нельзя отменить заказ, который уже отправлен или доставлен.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartAPIView(APIView):
    """
    API управления корзиной покупок (раздел 3.7 ТЗ: /api/cart/).

    Поддерживает методы:
    - GET: чтение содержимого корзины;
    - POST: добавление товара в корзину;
    - PATCH: обновление количества товара;
    - DELETE: очистка корзины.
    """

    permission_classes = [IsAuthenticated]

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
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        cart = Cart(request)

        already_in_cart = cart.cart.get(str(product.id), {}).get('quantity', 0)
        if already_in_cart + quantity > product.stock:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.add(product=product, quantity=quantity, override_quantity=False)
        return Response(
            {'detail': f'Товар «{product.name}» добавлен в корзину.'},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Обновить количество товара в корзине',
        description='Перезаписывает точное количество для указанного товара (PATCH по разделу 3.7 ТЗ).',
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
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        cart = Cart(request)

        if quantity > product.stock:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.add(product=product, quantity=quantity, override_quantity=True)
        return Response(
            {'detail': f'Количество для «{product.name}» обновлено.'},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Очистить корзину',
        responses={204: OpenApiResponse(description='Корзина успешно очищена')},
    )
    def delete(self, request: Request) -> Response:
        """Полностью очищает корзину."""
        cart = Cart(request)
        cart.clear()
        return Response(status=status.HTTP_204_NO_CONTENT)
