"""Сериализаторы DRF для эндпоинтов каталога товаров и категорий."""

from typing import Sequence
from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор категорий с метаданными."""

    class Meta:
        model = Category
        fields: Sequence[str] = ("id", "name", "slug", "parent")


class ProductListSerializer(serializers.ModelSerializer):
    """Сериализатор товаров для спискового вывода в REST API."""

    category: serializers.StringRelatedField = serializers.StringRelatedField()

    class Meta:
        model = Product
        fields: Sequence[str] = (
            "id",
            "name",
            "slug",
            "price",
            "category",
            "image",
            "stock",
            "is_active",
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    """Сериализатор полной информации о товаре для детального API."""

    category: CategorySerializer = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields: Sequence[str] = (
            "id",
            "name",
            "slug",
            "description",
            "price",
            "category",
            "image",
            "stock",
            "is_active",
            "created_at",
            "updated_at",
        )