"""JWT-аутентификация GraphQL-запросов.

Токены выпускает тот же rest_framework_simplejwt, что и для REST API —
нам не нужно плодить вторую систему аутентификации. Клиент логинится
через /api/users/login/, а полученный access-токен передаёт в GraphQL
как стандартный Bearer-токен.
"""

import logging
from collections.abc import Callable

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)

#: Префикс заголовка Authorization, за которым следует JWT.
AUTH_HEADER_PREFIX = 'Bearer '

#: Путь GraphQL-эндпоинта — middleware срабатывает только для него.
GRAPHQL_PATH_PREFIX = '/graphql/'


class GraphQLJWTAuthMiddleware:
    """Проставляет request.user по Bearer-токену для /graphql/.

    Для остальных путей middleware ничего не делает — их обслуживает
    стандартная сессионная аутентификация Django.

    Если токен отсутствует, истёк или невалиден — request.user остаётся
    тем, что установил Django (AnonymousUser или залогиненный сессионно).
    Резолверы сами решают, требовать ли аутентификацию.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Сохраняет следующий в цепочке обработчик (стандарт Django).

        Args:
            get_response: Callable, следующий в цепочке middleware.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Точка входа middleware.

        Args:
            request: Django HttpRequest.

        Returns:
            HttpResponse от следующего обработчика.
        """
        # Оптимизация: полностью пропускаем обработку для не-GraphQL запросов.
        if request.path.startswith(GRAPHQL_PATH_PREFIX):
            self._apply_jwt(request)
        return self.get_response(request)

    @staticmethod
    def _apply_jwt(request: HttpRequest) -> None:
        """Пытается подменить request.user по JWT-токену.

        Все ошибки (истёк, подпись не сошлась, пользователя удалили)
        считаются «нет токена» — молча выходим. Это правильно для GraphQL:
        ошибку аутентификации должен вернуть конкретный резолвер, а не 401
        на весь запрос.

        Args:
            request: Django HttpRequest, мутируется — при успехе
                в request.user кладётся найденный пользователь.
        """
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if not header.startswith(AUTH_HEADER_PREFIX):
            return

        raw_token = header[len(AUTH_HEADER_PREFIX):].strip()
        if not raw_token:
            return

        try:
            # AccessToken сам проверит подпись и срок действия.
            token = AccessToken(raw_token)
            user_id = token.get('user_id')
            if user_id is None:
                return

            user = get_user_model().objects.get(pk=user_id)
        except TokenError:
            # Истёк или невалидная подпись — оставляем как есть.
            return
        except get_user_model().DoesNotExist:
            # Токен валиден, но пользователя удалили.
            logger.warning('JWT refers to non-existent user_id=%s', user_id)
            return

        # Только активные пользователи получают доступ через API.
        if user.is_active:
            request.user = user