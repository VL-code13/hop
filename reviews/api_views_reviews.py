"""
Контроллеры Django REST Framework для отзывов на товары.

Реализует требования раздела 3.7 ТЗ (/api/products/<id>/reviews/):
- GET — список отзывов конкретного товара (доступен всем).
- POST — добавление отзыва (только авторизованным JWT, купившим товар).

Отключение пагинации: отзывы одного товара возвращаются одним списком,
без обёртки {count, next, previous, results}, чтобы упростить фронтенд.
"""

from typing import Any

from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError

from orders.models import Order
from products.models import Product

from .models import Review
from .serializers import ReviewSerializer


class ProductReviewsAPIView(generics.ListCreateAPIView):
    """
    Эндпоинт просмотра и добавления отзывов к товару (раздел 3.7 ТЗ).

    GET  — список отзывов. Доступен без авторизации (permissions.AllowAny).
    POST — добавление отзыва. Требует JWT (permissions.IsAuthenticated).

    URL: /api/products/<product_id>/reviews/
    product_id берётся из self.kwargs (прокидывается из urls.py).
    """

    serializer_class = ReviewSerializer

    # Отключаем пагинацию DRF. По умолчанию ListCreateAPIView оборачивает
    # результат в {count, next, previous, results}. Для отзывов одного товара
    # это лишнее — возвращаем простой список. Это также чинит тест, который
    # проверяет len(response.data) == 1 (без обёртки результатов).
    pagination_class = None

    def get_permissions(self) -> list[Any]:
        """
        Разные пермишны для разных HTTP-методов.

        GET  — открыт для всех (AllowAny), т.к. отзывы публичны.
        POST — требует авторизацию (IsAuthenticated), т.к. нужно знать,
               кто оставляет отзыв.

        DRF вызывает этот метод до обработки запроса и применяет
        возвращённый список пермишнов.
        """
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self) -> Any:
        """
        Возвращает отзывы конкретного товара, отсортированные по новизне.

        select_related('user') — подхватывает связанного пользователя
        одним JOIN-запросом, чтобы избежать N+1 при сериализации
        поля user (имя пользователя в отзыве).
        """
        product_id = self.kwargs.get('product_id')
        return (
            Review.objects.filter(product_id=product_id)
            .select_related('user')          # Предзагрузка User — избегаем N+1
            .order_by('-created_at')         # Новые отзывы первыми
        )

    def perform_create(self, serializer: Any) -> None:
        """
        Создаёт отзыв с проверкой бизнес-правил (раздел 3.2 ТЗ).

        Вызывается DRF после валидации сериализатора, но до сохранения.
        Здесь мы добавляем проверки, которые сериализатор не может сделать:
        1. Купил ли пользователь товар (Order со статусом PAID/DELIVERED).
        2. Оставлял ли уже отзыв (UniqueConstraint на уровне БД — дублируем
           здесь, чтобы вернуть красивую JSON-ошибку, а не 500).

        permission_classes = [IsAuthenticated] для POST гарантирует,
        что request.user — авторизованный пользователь.
        Аннотация `user: Any` сужает тип для mypy без рантайм-проверок.
        """
        # IsAuthenticated в get_permissions() уже отсёк AnonymousUser.
        user: Any = self.request.user

        # Достаём product_id из URL-kwargs и находим активный товар.
        product_id = self.kwargs.get('product_id')
        product = generics.get_object_or_404(Product, id=product_id, is_active=True)

        # --- Проверка 1: факт покупки ---
        # Ищем заказ с данным товаром у данного пользователя,
        # статус которого PAID или DELIVERED.
        has_purchased = Order.objects.filter(
            user=user,
            items__product=product,
            status__in=[Order.Status.PAID, Order.Status.DELIVERED],
        ).exists()

        if not has_purchased:
            # PermissionDenied → DRF вернёт 403 с сообщением в JSON.
            raise PermissionDenied(
                'Оставить отзыв можно только на товар, который вы приобрели и оплатили.'
            )

        # --- Проверка 2: повторный отзыв ---
        # UniqueConstraint в модели не даст сохранить дубль, но здесь
        # мы возвращаем осмысленную ошибку 400 вместо IntegrityError (500).
        if Review.objects.filter(product=product, user=user).exists():
            raise ValidationError('Вы уже оставляли отзыв на данный товар.')

        # Сохраняем отзыв, проставляя user и product из контекста запроса.
        # Сериализатор не требует этих полей от клиента — они берутся из URL и JWT.
        serializer.save(user=user, product=product)
