"""
Контроллеры Django REST Framework для отзывов на товары.

Реализует требования раздела 3.7 ТЗ (/api/products/<id>/reviews/):
- GET  — публичный список отзывов конкретного товара.
- POST — добавление отзыва (валидация факта покупки делегирована в ReviewSerializer).
"""

from typing import Any

from rest_framework import generics, permissions

from products.models import Product

from .models import Review
from .serializers import ReviewSerializer


class ProductReviewsAPIView(generics.ListCreateAPIView):
    """
    Эндпоинт просмотра и добавления отзывов к товару (раздел 3.7 ТЗ).

    GET  — доступен всем (AllowAny).
    POST — требует JWT-аутентификации (IsAuthenticated).
    Пагинация отключена для отдачи плоского списка отзывов к товару.
    """

    serializer_class = ReviewSerializer
    pagination_class = None

    def get_permissions(self) -> list[Any]:
        """Разграничение прав: просмотр открыт всем, добавление — авторизованным."""
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_product(self) -> Product:
        """Вспомогательный метод получения активного товара по ID из URL."""
        product_id = self.kwargs.get('product_id')
        return generics.get_object_or_404(Product, id=product_id, is_active=True)

    def get_queryset(self) -> Any:
        """
        Возвращает отзывы конкретного товара с JOIN автора во избежание N+1 запросов.
        """
        product_id = self.kwargs.get('product_id')
        return Review.objects.filter(product_id=product_id).select_related('user').order_by('-created_at')

    def get_serializer_context(self) -> dict[str, Any]:
        """
        Передаёт в сериализатор HTTP-запрос и инстанс товара для выполнения валидации.
        """
        # Преобразуем Mapping в мутабельный dict для корректной типизации в mypy
        context: dict[str, Any] = dict(super().get_serializer_context())
        if self.request.method == 'POST':
            context['product'] = self.get_product()
        return context

    def perform_create(self, serializer: Any) -> None:
        """
        Создаёт отзыв. Вся проверка прав и факта покупки выполняется внутри serializer.is_valid().
        """
        serializer.save()
