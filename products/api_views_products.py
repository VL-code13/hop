"""
Контроллеры Django REST Framework для каталога товаров.

Реализует требования раздела 3.7 ТЗ (/api/products/ и /api/products/<id>/).
"""
from typing import Any

from django.db.models import Avg, QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import AllowAny

from .models import Product
from .serializers import ProductDetailSerializer, ProductListSerializer

# Лучшие практики: Разделение спискового и детального сериализаторов (get_serializer_class) позволяет не
# отдавать тяжелое текстовое описание в общем листинге товаров, экономя сетевой трафик.


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра списка и деталей товаров каталога (раздел 3.7 ТЗ).

    Поддерживает фильтрацию по категории и диапазону цен,
    поиск по названию и описанию, сортировку по цене, дате
    создания и рейтингу.
    """

    # lookup_field: str = 'slug' # если хзахотим по слагу вместо ИД
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
        return (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .annotate(avg_rating=Avg('review__rating'))
            .order_by('-created_at')
        )

    def get_serializer_class(self) -> Any:
        """Динамический выбор сериализатора: облегченный для списка, полный для детали."""
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
