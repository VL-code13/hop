"""
Контроллеры Django REST Framework для каталога товаров.

Реализует требования раздела 3.7 ТЗ (/api/products/ и /api/products/<id>/).
"""

from typing import Any

from django.db.models import Avg, QuerySet
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore[import-untyped]
from rest_framework import filters, viewsets
from rest_framework.permissions import AllowAny

from .models import Product
from .serializers import ProductDetailSerializer, ProductListSerializer


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра списка и деталей товаров каталога (раздел 3.7 ТЗ).

    Поддерживает:
    - фильтрацию по категории (category__slug) и диапазону цен;
    - поиск по названию и описанию (?search=...);
    - сортировку по цене, новизне и расчетному рейтингу (?ordering=...).
    """

    permission_classes: list = [AllowAny]
    filter_backends: list = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields: dict = {
        'category__slug': ['exact'],
        'price': ['gte', 'lte'],
    }
    search_fields: list[str] = ['name', 'description']
    ordering_fields: list[str] = ['price', 'created_at', 'avg_rating', 'name']
    ordering = ['-created_at']

    def get_queryset(self) -> QuerySet[Product]:
        """
        Возвращает активные товары с предварительной загрузкой категории (JOIN)
        и аннотированием среднего рейтинга по связанным отзывам.
        """
        return (
            Product.objects.filter(is_active=True)
            .select_related('category')
            # Исправлено: 'reviews__rating' (было 'review__rating') в соответствии с related_name
            .annotate(avg_rating=Avg('reviews__rating'))
            .order_by('-created_at')
        )

    def get_serializer_class(self) -> Any:
        """
        Динамический выбор сериализатора:
        - ProductDetailSerializer для детального просмотра (action == 'retrieve')
        - ProductListSerializer для общего каталога (action == 'list')
        """
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer