"""Публичные GraphQL-запросы для пользователей."""

import strawberry
from strawberry.types import Info

from users.graphql.types import UserType


@strawberry.type
class UserQuery:
    """Запросы, доступные любому аутентифицированному пользователю."""

    @strawberry.field
    def me(self, info: Info) -> UserType | None:
        """Возвращает текущего пользователя.

        Полезно для фронтенда: один GraphQL-запрос после логина даёт
        профиль без необходимости знать REST-эндпоинт /api/users/me/.

        Args:
            info: GraphQL-контекст.

        Returns:
            UserType текущего пользователя или None, если он не аутентифицирован.
        """
        user = info.context.user
        if not user.is_authenticated:
            return None
        return UserType.from_django(user)