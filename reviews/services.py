"""Сервисный слой отзывов.

Содержит бизнес-правило раздела 3.2 ТЗ: оставить отзыв можно только
после оплаты (`PAID`) или получения (`DELIVERED`) заказа.

Функция вынесена из представлений, чтобы:
1. Избежать циклических импортов между `products` и `reviews`;
2. Переиспользовать логику в веб-интерфейсе, REST API и GraphQL;
3. Тестировать бизнес-правило без HTTP-клиента.
"""

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from orders.models import Order
from products.models import Product
from reviews.models import Review

# Тип `request.user`: либо реальный пользователь, либо аноним.
# django-stubs типизирует `HttpRequest.user` как `AbstractBaseUser | AnonymousUser`,
# повторяем этот union, чтобы сигнатура совпадала.
UserLike = AbstractBaseUser | AnonymousUser


def get_review_permissions(
    user: UserLike,
    product: Product,
) -> tuple[bool, bool]:
    """Определяет права пользователя на отзыв о конкретном товаре.

    Инкапсулирует бизнес-правило раздела 3.2 ТЗ: оставить отзыв может
    только авторизованный пользователь, оплативший или получивший заказ
    с этим товаром. Повторный отзыв невозможен (см. `UniqueConstraint`
    на модели `Review`).

    Используется в `ProductDetailView` для передачи в шаблон флагов
    `can_review` и `has_existing_review`.

    Args:
        user: Текущий пользователь из `request.user`. Может быть
            анонимным — тогда возвращается `(False, False)` без
            обращения к БД.
        product: Товар, для которого проверяются права.

    Returns:
        tuple[bool, bool]: Кортеж из двух флагов:

        - **can_review** (bool): True, если пользователь может оставить
          отзыв (авторизован, ещё не оставлял, имеет оплаченный или
          доставленный заказ на товар).
        - **has_existing_review** (bool): True, если отзыв уже оставлен.

    Examples:
        Для анонима:
        >>> get_review_permissions(AnonymousUser(), product)
        (False, False)

        Для покупателя без заказа:
        >>> get_review_permissions(user_without_order, product)
        (False, False)

        Для покупателя с оплаченным заказом:
        >>> get_review_permissions(user_with_paid_order, product)
        (True, False)

        Для покупателя, уже оставившего отзыв:
        >>> get_review_permissions(user_with_review, product)
        (False, True)
    """
    if not user.is_authenticated:
        return False, False

    has_existing_review: bool = Review.objects.filter(
        product=product,
        user=user,
    ).exists()
    if has_existing_review:
        return False, True

    has_purchased: bool = Order.objects.filter(
        user=user,
        items__product=product,
        status__in=[Order.Status.PAID, Order.Status.DELIVERED],
    ).exists()
    return has_purchased, False
