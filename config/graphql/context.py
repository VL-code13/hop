"""Контекст GraphQL-запросов и кастомное представление Django.

Каждый запрос к /graphql/ получает собственный экземпляр GraphQLContext.
Резолверы обращаются к нему через `info.context`, что даёт доступ к
request, текущему пользователю и per-request кешу.

Кастомный контекст задаётся переопределением метода get_context в
подклассе GraphQLView — параметр context_getter в Django-интеграции
Strawberry больше не поддерживается.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from django.http import HttpRequest, HttpResponse
from strawberry.django.views import GraphQLView

if TYPE_CHECKING:
    from django.contrib.auth.models import User


@dataclass
class GraphQLContext:
    """Контекст одного GraphQL-запроса.

    Attributes:
        request: HttpRequest Django — источник заголовков, сессии, user.
        _cache: Per-request кеш. Используется резолверами для мемоизации
            (например, чтобы не считать метрики дважды в одном запросе).
    """

    request: HttpRequest
    _cache: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def user(self) -> 'User':
        """Текущий пользователь.

        Достаётся из request.user, который установлен либо Django-сессией,
        либо нашим GraphQLJWTAuthMiddleware (для запросов с JWT).

        Returns:
            Экземпляр User (или AnonymousUser, если не аутентифицирован).
        """
        return self.request.user

    def cache_get(self, key: str) -> Any:
        """Возвращает значение из per-request кеша или None."""
        return self._cache.get(key)

    def cache_set(self, key: str, value: Any) -> None:
        """Сохраняет значение в per-request кеш."""
        self._cache[key] = value


class HopBarleyGraphQLView(GraphQLView):
    """GraphQLView с кастомным контекстом.

    Strawberry в Django-интеграции не принимает `context_getter` в as_view().
    Вместо этого нужно унаследоваться от GraphQLView и переопределить
    get_context — именно этот метод вызывается в начале каждого запроса.
    """

    def get_context(self, request: HttpRequest, response: HttpResponse) -> GraphQLContext:
        """Формирует контекст для текущего GraphQL-запроса.

        Args:
            request: Django HttpRequest.
            response: Django HttpResponse (передаётся Strawberry).

        Returns:
            Свежий GraphQLContext для запроса.
        """
        return GraphQLContext(request=request)
