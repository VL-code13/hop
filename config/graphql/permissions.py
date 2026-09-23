"""Права доступа для GraphQL-резолверов.

Аналитика — это внутренние метрики магазина. Публичный пользователь не
должен видеть ни выручку, ни количество повторных покупок, ни остатки
на складе. Все аналитические резолверы оборачиваются в @staff_only.

В REST за это отвечают permissions-классы DRF (IsAdminUser и т.п.).
В GraphQL мы делаем то же самое, но через декоратор — потому что
Graphene/Strawberry не имеют встроенного эквивалента DRF-permissions.
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from graphql import GraphQLError
from strawberry.types import Info

F = TypeVar('F', bound=Callable[..., Any])


def staff_only(resolver: F) -> F:
    """Декоратор: разрешает вызов только аутентифицированному staff-пользователю.

    Используется так:
        @strawberry.field
        @staff_only
        def order_metrics(self, info: Info) -> OrderMetrics: ...

    Проверка выполняется ДО тела резолвера — если пользователь не staff,
    резолвер не выполнится вообще, а GraphQL вернёт ошибку.

    Args:
        resolver: Резолвер, который нужно защитить.

    Returns:
        Обёрнутый резолвер с проверкой прав.

    Raises:
        GraphQLError: Если пользователь не аутентифицирован или не staff.
            Extensions.code = 'UNAUTHENTICATED' для гостей,
            Extensions.code = 'FORBIDDEN' для не-staff.
    """

    @functools.wraps(resolver)
    def wrapper(self: Any, info: Info, *args: Any, **kwargs: Any) -> Any:
        user = info.context.user

        if not user.is_authenticated:
            raise GraphQLError(
                'Требуется аутентификация. Передайте JWT в заголовке Authorization.',
                extensions={'code': 'UNAUTHENTICATED'},
            )

        if not user.is_staff:
            raise GraphQLError(
                'Доступ к аналитике разрешён только сотрудникам.',
                extensions={'code': 'FORBIDDEN'},
            )

        return resolver(self, info, *args, **kwargs)

    return wrapper  # type: ignore[return-value]