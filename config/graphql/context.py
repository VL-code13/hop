"""Контекст GraphQL-запросов.

Каждый запрос к /graphql/ получает собственный экземпляр GraphQLContext.
Резолверы обращаются к нему через `info.context`, что даёт доступ к
request, текущему пользователю и per-request кешу.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.http import HttpRequest

    # Импортируем User только для типизации — не тянем модель в рантайме.
    from django.contrib.auth.models import User


@dataclass
class GraphQLContext:
    """Контекст одного GraphQL-запроса.

    Attributes:
        request: HttpRequest Django — источник заголовков, сессии, user.
        _cache: Per-request кеш. Используется резолверами для мемоизации
            (например, чтобы не считать метрики дважды в одном запросе).
    """

    request: 'HttpRequest'
    _cache: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def user(self) -> 'User':
        """Текущий пользователь.

        Достаётся из request.user, который установлен либо Django-сессией,
        либо нашим GraphQLJWTAuthMiddleware (для REST-подобных запросов с JWT).

        Returns:
            Экземпляр User (или AnonymousUser, если пользователь не аутентифицирован).
        """
        return self.request.user

    def cache_get(self, key: str) -> Any:
        """Возвращает значение из per-request кеша или None."""
        return self._cache.get(key)

    def cache_set(self, key: str, value: Any) -> None:
        """Сохраняет значение в per-request кеш.

        Кеш живёт ровно один GraphQL-запрос — этого достаточно, чтобы
        избежать повторных запросов к БД в пределах одного ответа.
        """
        self._cache[key] = value


def get_context(request: 'HttpRequest', response: Any = None) -> GraphQLContext:
    """Фабрика контекста для Strawberry.

    Strawberry вызывает её в начале каждого запроса. Дополнительный
    аргумент `response` — стандарт Strawberry, не используем его.

    Args:
        request: Django HttpRequest.
        response: HttpResponse (передаётся Strawberry, не нужен).

    Returns:
        Свежий GraphQLContext для запроса.
    """
    return GraphQLContext(request=request)