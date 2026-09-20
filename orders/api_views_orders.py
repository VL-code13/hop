"""
Контроллеры Django REST Framework для заказов и корзины.

Реализует требования раздела 3.7 ТЗ:
- /api/orders/  — CRUD заказов пользователя (JWT-авторизация).
- /api/cart/    — управление сессионной корзиной через API.

Документирование схем OpenAPI — раздел 3.8 ТЗ (drf-spectacular @extend_schema).
"""

from typing import Any

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

    Доступно только авторизованным пользователям (IsAuthenticated).
    Пользователь видит и управляет только своими заказами —
    get_queryset фильтрует по self.request.user.

    Поддерживаемые методы:
    - GET    (list)   — список заказов пользователя.
    - GET    (retrieve) — детали конкретного заказа.
    - POST   (create) — создание заказа из сессионной корзины.
    - PATCH  (partial_update) — частичное обновление (не реализовано).
    - DELETE (destroy) — отмена заказа (перевод в CANCELLED).

    Аннотация `user: Any` сужает тип request.user для mypy:
    IsAuthenticated уже отсёк AnonymousUser, Any убирает ошибки без рантайм-проверок.
    """

    permission_classes = [IsAuthenticated]
    # Ограничиваем HTTP-методы — не все из CRUD нужны.
    # PUT (полное обновление) отключён, т.к. заказ нельзя редактировать целиком.
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self) -> Any:
        """
        Возвращает заказы текущего пользователя, отсортированные по новизне.

        prefetch_related('items__product') — подгружает позиции заказа
        и связанные товары двухуровневым JOIN, чтобы избежать N+1 при сериализации.
        Без prefetch каждый заказ делал бы отдельный запрос за позициями.
        """
        user: Any = self.request.user
        return Order.objects.filter(user=user).prefetch_related('items__product').order_by('-created_at')

    def get_serializer_class(self) -> Any:
        """
        Выбирает сериализатор в зависимости от действия.

        create — OrderCreateSerializer (валидация данных для создания).
        Остальные (list, retrieve, patch) — OrderSerializer (полный вывод).
        """
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request: Request) -> Response:
        """
        Создаёт заказ из сессионной корзины пользователя.

        Алгоритм:
        1. Проверяем, что корзина не пуста.
        2. Валидируем данные доставки (OrderCreateSerializer).
        3. Проверяем остатки на складе ДО транзакции.
        4. Внутри transaction.atomic() создаём заказ, позиции, списываем остатки.
        5. Очищаем корзину.
        """
        user: Any = request.user

        cart = Cart(request)
        if len(cart) == 0:
            return Response(
                {'detail': 'Невозможно оформить заказ: корзина пуста.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Валидируем адрес доставки и способ оплаты.
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # --- Проверка остатков ДО транзакции ---
        # Если остатков не хватает — возвращаем 400 без запуска atomic().
        # Это дешевле, чем откатывать начатую транзакцию.
        for item in cart:
            if item['product'].stock < item['quantity']:
                return Response(
                    {'detail': f'Недостаточно товара «{item["product"].name}» (остаток: {item["product"].stock}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # --- Создание заказа в одной транзакции ---
        # atomic() гарантирует целостность: если упадёт создание любой позиции,
        # весь заказ (включая списание остатков) откатится.
        with transaction.atomic():
            # Заголовок заказа. Статус PENDING — ожидает оплаты.
            order = Order.objects.create(
                user=user,
                shipping_address=serializer.validated_data['shipping_address'],
                payment_method=serializer.validated_data.get('payment_method', Order.PaymentMethod.CARD),
                total_price=cart.get_total_price(),
                status=Order.Status.PENDING,
            )

            # Создаём позиции и списываем остатки.
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    price=item['price'],  # Цена на момент заказа (фиксируется)
                    quantity=item['quantity'],
                )
                # Уменьшаем остаток на складе.
                item['product'].stock -= item['quantity']
                item['product'].save(update_fields=['stock'])

        # Очищаем корзину — заказ оформлен, товары перенесены в заказ.
        cart.clear()
        # Возвращаем созданный заказ через OrderSerializer (с полными деталями).
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def destroy(self, request: Request) -> Response:
        """
        Отмена заказа — переводит статус в CANCELLED, не удаляет запись.

        Нельзя отменить заказ, который уже отправлен (SHIPPED)
        или доставлен (DELIVERED) — возвращаем 400.
        """
        # get_object() берёт заказ из get_queryset() — с фильтром по user.
        order = self.get_object()
        if order.status in [Order.Status.SHIPPED, Order.Status.DELIVERED]:
            return Response(
                {'detail': 'Нельзя отменить заказ, который уже отправлен или доставлен.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Меняем статус, не удаляем — сохраняем историю.
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartAPIView(APIView):
    """
    API управления корзиной покупок (раздел 3.7 ТЗ: /api/cart/).

    Корзина хранится в сессии, но API требует авторизацию (IsAuthenticated),
    чтобы привязать сессию к конкретному пользователю.

    Методы:
    - GET    — содержимое корзины (товары, количество, итоги).
    - POST   — добавить товар в корзину.
    - PATCH  — перезаписать количество товара (override).
    - DELETE — полностью очистить корзину.

    @extend_schema — описание для автогенерации OpenAPI/Swagger (раздел 3.8 ТЗ).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Получить содержимое корзины',
        description='Возвращает список товаров в корзине, их количество и общую стоимость.',
        responses={200: CartResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        """
        Возвращает содержимое корзины в формате:
        {items: [...], total_items: N, total_price: "1234.56"}
        """
        cart = Cart(request)
        # Собираем список товаров для JSON-ответа.
        # Cart итерируется по словарю session, каждый item — словарь с product, price, quantity.
        items = [
            {
                'product_id': item['product'].id,
                'product_name': item['product'].name,
                'price': item['price'],  # Строковое Decimal (фиксируется при добавлении)
                'quantity': item['quantity'],
                'total_price': item['total_price'],  # price * quantity (Decimal)
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
            200: OpenApiResponse(description='Товар успешно добавлен'),
            400: OpenApiResponse(description='Недостаточно товара на складе'),
        },
    )
    def post(self, request: Request) -> Response:
        """
        Добавляет товар в корзину.

        Проверяет, что суммарное количество (уже в корзине + новое) не превышает остаток.
        override_quantity=False — количество прибавляется к существующему.
        """
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        cart = Cart(request)

        # Сколько этого товара уже в корзине.
        # cart.cart — внутренний dict: {product_id: {quantity, price}}.
        already_in_cart = cart.cart.get(str(product.id), {}).get('quantity', 0)

        # Проверка: текущее количество + новое не больше остатка на складе.
        if already_in_cart + quantity > product.stock:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # override_quantity=False — прибавляем quantity к уже имеющемуся.
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
        """
        Перезаписывает точное количество товара в корзине.

        В отличие от POST, здесь override_quantity=True —
        старое количество игнорируется, ставится новое.
        """
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        cart = Cart(request)

        # Проверяем только новое количество (старое не учитывается).
        if quantity > product.stock:
            return Response(
                {'detail': f'Недостаточно товара на складе (в наличии: {product.stock}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # override_quantity=True — заменяем, а не прибавляем.
        cart.add(product=product, quantity=quantity, override_quantity=True)
        return Response(
            {'detail': f'Количество для «{product.name}» обновлено.'},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Очистить корзину',
        description='Полностью очищает сессионную корзину покупок.',
        responses={200: OpenApiResponse(description='Корзина очищена')},
    )
    def delete(self, request: Request) -> Response:
        """Полностью очищает содержимое корзины (все позиции)."""
        cart = Cart(request)
        cart.clear()
        return Response(
            {'detail': 'Корзина очищена.'},
            status=status.HTTP_200_OK,
        )
