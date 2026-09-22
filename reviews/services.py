"""Сервисный слой отзывов.

Содержит бизнес-правило раздела 3.2 ТЗ: оставить отзыв можно только
после оплаты (`PAID`) или получения (`DELIVERED`) заказа.
"""

from typing import cast

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from orders.models import Order
from products.models import Product
from reviews.models import Review


def get_review_permissions(
    user: AbstractBaseUser | AnonymousUser,
    product: Product,
) -> tuple[bool, bool]:
    """Определяет права пользователя на отзыв о конкретном товаре.

    Инкапсулирует бизнес-правило раздела 3.2 ТЗ: оставить отзыв может
    только авторизованный пользователь, оплативший или получивший заказ
    с этим товаром. Повторный отзыв невозможен (см. `UniqueConstraint`
    на модели `Review`).

    Args:
        user: Текущий пользователь из `request.user`. Может быть
            анонимным — тогда возвращается `(False, False)` без
            обращения к БД.
        product: Товар, для которого проверяются права.

    Returns:
        tuple[bool, bool]: `(can_review, has_existing_review)`.

        - **can_review**: True, если пользователь может оставить отзыв.
        - **has_existing_review**: True, если отзыв уже оставлен.
    """
    if not user.is_authenticated:
        return False, False

    # После проверки is_authenticated пользователь гарантированно
    # авторизован, но django-stubs типизирует request.user как
    # AbstractBaseUser | AnonymousUser. cast сужает тип для mypy;
    # User, которую ожидает ForeignKey в фильтрах (issue #561).
    auth_user = cast(AbstractBaseUser, user)

    has_existing_review: bool = Review.objects.filter(
        product=product,
        user=auth_user,  # type: ignore[misc]
    ).exists()
    if has_existing_review:
        return False, True

    has_purchased: bool = Order.objects.filter(
        user=auth_user,  # type: ignore[misc]
        items__product=product,
        status__in=[Order.Status.PAID, Order.Status.DELIVERED],
    ).exists()
    return has_purchased, False
