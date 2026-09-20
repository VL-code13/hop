"""
Сериализаторы Django REST Framework для каталога товаров и категорий.

Реализует требования раздела 3.7 ТЗ (/api/products/ и /api/products/<id>/).
"""

from collections.abc import Sequence

from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор категорий с выводом вложенности (parent)."""

    class Meta:
        model = Category
        fields: Sequence[str] = ('id', 'name', 'slug', 'parent')


class ProductListSerializer(serializers.ModelSerializer):
    """
    Краткая информация о товаре для списка /api/products/.
    Не включает тяжелое поле `description`, экономя сетевой трафик листинга.
    """

    # Извлекаем строковое название категории вместо вложенного словаря
    category = serializers.CharField(source='category.name', read_only=True)
    # Поле avg_rating рассчитывается динамически через аннотацию в ViewSet
    avg_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields: Sequence[str] = (
            'id',
            'slug',
            'name',
            'price',
            'image',
            'category',
            'avg_rating',
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Полная информация о товаре для эндпоинта /api/products/<id>/.
    Включает полное описание, категорию с предком и аудитные поля.
    """

    # В детальном виде отдаем вложенный объект категории
    category = CategorySerializer(read_only=True)
    avg_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields: Sequence[str] = (
            'id',
            'slug',
            'name',
            'description',
            'price',
            'image',
            'stock',
            'is_active',
            'category',
            'avg_rating',
            'created_at',
            'updated_at',
        )