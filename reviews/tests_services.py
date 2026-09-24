# reviews/tests_services.py
"""Тесты сервисного слоя отзывов (`reviews/services.py`).

Проверяют бизнес-правило раздела 3.2 ТЗ без HTTP-клиента.
"""

import pytest
from django.contrib.auth.models import AnonymousUser

from reviews.services import get_review_permissions


@pytest.mark.django_db
class TestGetReviewPermissions:
    """Набор тестов для `get_review_permissions`."""

    def test_anonymous_user_cannot_review(self, product):
        """Анонимный пользователь не может оставить отзыв."""
        can, has = get_review_permissions(AnonymousUser(), product)
        assert can is False
        assert has is False

    def test_user_without_order_cannot_review(self, user, product):
        """Авторизованный пользователь без заказа не может оставить отзыв."""
        can, has = get_review_permissions(user, product)
        assert can is False
        assert has is False

    def test_user_with_pending_order_cannot_review(self, user, product):
        """Заказ в статусе PENDING не даёт права на отзыв."""
        from orders.models import Order, OrderItem

        order = Order.objects.create(user=user, status=Order.Status.PENDING)
        OrderItem.objects.create(order=order, product=product, price=product.price, quantity=1)

        can, has = get_review_permissions(user, product)
        assert can is False
        assert has is False

    def test_user_with_paid_order_can_review(self, paid_order):
        """Оплаченный заказ даёт право на отзыв."""
        product = paid_order.items.first().product
        can, has = get_review_permissions(paid_order.user, product)
        assert can is True
        assert has is False

    def test_user_with_delivered_order_can_review(self, delivered_order):
        """Доставленный заказ даёт право на отзыв."""
        product = delivered_order.items.first().product
        can, has = get_review_permissions(delivered_order.user, product)
        assert can is True
        assert has is False

    def test_user_with_existing_review(self, review):
        """Если отзыв уже есть — can_review=False, has_existing_review=True."""
        can, has = get_review_permissions(review.user, review.product)
        assert can is False
        assert has is True
