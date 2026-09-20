"""
Сериализаторы Django REST Framework для системы отзывов.

Реализует требования раздела 3.7 ТЗ (/api/products/<id>/reviews/).
"""

from collections.abc import Sequence

from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """Сериализатор отзывов с указанием автора и валидацией рейтинга."""

    user: serializers.ReadOnlyField = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Review
        fields: Sequence[str] = ('id', 'user', 'product', 'rating', 'comment', 'created_at')
        read_only_fields: Sequence[str] = ('id', 'user', 'product', 'created_at')

    def validate_rating(self, value: int) -> int:
        """Проверка диапазона оценки от 1 до 5."""
        if not (1 <= value <= 5):
            raise serializers.ValidationError('Оценка должна быть в диапазоне от 1 до 5.')
        return value
