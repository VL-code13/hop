"""
Контроллеры Django REST Framework для отзывов на товары.

Реализует требования раздела 3.7 ТЗ (/api/products/<id>/reviews/).
"""

from typing import Any

from drf_spectacular.openapi import AutoSchema
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError

from orders.models import Order
from products.models import Product
from .models import Review
from .serializers import ReviewSerializer


class ProductReviewsAPIView(generics.ListCreateAPIView):
    """
    Эндпоинт просмотра и добавления отзывов к товару (раздел 3.7 ТЗ).

    GET: доступен всем (список отзывов конкретного товара).
    POST: доступен только авторизованным (JWT), купившим данный товар.
    """
    schema = AutoSchema()
    serializer_class = ReviewSerializer

    def get_permissions(self) -> list[Any]:
        """Чтение открыто для всех, публикация — только для авторизованных."""
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self) -> Any:
        """Фильтрует отзывы по идентификатору товара из URL."""
        product_id = self.kwargs.get('product_id')
        return (
            Review.objects.filter(product_id=product_id)
            .select_related('user')
            .order_by('-created_at')
        )

    def perform_create(self, serializer: Any) -> None:
        """Валидирует факт покупки перед сохранением отзыва через API."""
        product_id = self.kwargs.get('product_id')
        product = generics.get_object_or_404(Product, id=product_id, is_active=True)

        has_purchased = Order.objects.filter(
            user=self.request.user,
            items__product=product,
            status__in=[Order.Status.PAID, Order.Status.DELIVERED],
        ).exists()

        if not has_purchased:
            raise PermissionDenied('Оставить отзыв можно только на товар, который вы приобрели и оплатили.')

        if Review.objects.filter(product=product, user=self.request.user).exists():
            raise ValidationError('Вы уже оставляли отзыв на данный товар.')

        serializer.save(user=self.request.user, product=product)
