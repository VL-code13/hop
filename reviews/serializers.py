"""
Сериализаторы Django REST Framework для системы отзывов.

Реализует требования разделов:
- 3.2 («Отзывы с рейтингами 1–5, возможность оставить отзыв только после покупки»)
- 3.7 («REST API: /api/products/<id>/reviews/»)
"""

from collections.abc import Sequence
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from orders.models import Order
from products.models import Product

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """
    Сериализатор отзывов покупателей.

    Инкапсулирует ключевую бизнес-логику:
    1. Валидация рейтинга (целое число от 1 до 5).
    2. Проверка факта покупки и оплаты товара пользователем (Order.Status: PAID/DELIVERED).
    3. Проверка уникальности отзыва (один пользователь — один отзыв на товар).
    4. Автоматическая привязка пользователя и товара при сохранении.
    """

    user: serializers.ReadOnlyField = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Review
        fields: Sequence[str] = ('id', 'user', 'product', 'rating', 'comment', 'created_at')
        read_only_fields: Sequence[str] = ('id', 'user', 'product', 'created_at')

    def validate_rating(self, value: int) -> int:
        """Валидация диапазона оценки (от 1 до 5 включительно)."""
        if not (1 <= value <= 5):
            raise ValidationError('Оценка должна быть в диапазоне от 1 до 5.')
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Комплексная валидация бизнес-правил перед публикацией отзыва (раздел 3.2 ТЗ).
        """
        request = self.context.get('request')
        product = self.context.get('product')

        if not request or not product:
            raise ValidationError('Отсутствует контекст запроса или целевой товар.')

        user = request.user
        if not user.is_authenticated:
            raise PermissionDenied('Оставлять отзывы могут только авторизованные пользователи.')

        # Бизнес-правило 1: проверка факта покупки и оплаты товара
        has_purchased: bool = Order.objects.filter(
            user=user,
            items__product=product,
            status__in=[Order.Status.PAID, Order.Status.DELIVERED],
        ).exists()

        if not has_purchased:
            # Выбрасываем PermissionDenied для возврата 403 Forbidden по ТЗ
            raise PermissionDenied('Оставить отзыв можно только на товар, который вы приобрели и оплатили.')

        # Бизнес-правило 2: проверка на повторный отзыв (UniqueConstraint)
        # Исключаем текущий объект при обновлении (если когда-то понадобится редактирование)
        existing_review = Review.objects.filter(product=product, user=user)
        if self.instance:
            existing_review = existing_review.exclude(pk=self.instance.pk)

        if existing_review.exists():
            raise ValidationError('Вы уже оставляли отзыв на данный товар.')

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Review:
        """
        Создание отзыва с автоматическим проставлением user и product из контекста.
        """
        user = self.context['request'].user
        product: Product = self.context['product']

        return Review.objects.create(
            user=user,
            product=product,
            rating=validated_data['rating'],
            comment=validated_data['comment'],
        )
