"""GraphQL-типы для пользователей и аналитики поведения."""

import strawberry
import strawberry_django
from django.contrib.auth.models import User


@strawberry_django.type(User)
class UserType:
    """Публичный профиль пользователя.

    Отдаём только безопасные поля — ни пароля, ни last_login, ни is_superuser.
    """

    id: strawberry.ID
    username: strawberry.auto
    email: strawberry.auto
    first_name: strawberry.auto
    last_name: strawberry.auto
    date_joined: strawberry.auto


@strawberry.type
class UserActivityMetrics:
    """Метрики активности пользователей за период."""

    new_users: int
    active_buyers: int
    repeat_buyers: int
    repeat_purchase_rate: float
    orders_per_buyer: float
