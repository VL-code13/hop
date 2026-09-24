"""Кеширование тяжёлых аналитических метрик GraphQL.

Декоратор @cache_metric кеширует результат резолвера по его аргументам.
Ключ строится из домена (prefix), имени функции и хеша kwargs.

Порядок применения декораторов:
    @strawberry.field
    @staff_only              # проверка прав — ДО кеша
    @cache_metric(...)       # кеш — внутри
    def resolver(...): ...

Кеширование — необязательное звено: если backend недоступен, резолвер
всё равно выполнится, а результат не закешируется. Аналитика не должна
падать из-за проблем с кешем.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)


def _make_key(prefix: str, func_name: str, kwargs: dict[str, Any]) -> str:
    """Строит стабильный ключ кеша из имени функции и её аргументов.

    Аргументы нормализуются через JSON с сортировкой ключей, чтобы
    вызовы с одинаковыми данными, но разным порядком kwargs, давали
    один и тот же ключ.

    Args:
        prefix: Домен метрики (orders / products / users).
        func_name: Имя резолвера.
        kwargs: Аргументы вызова резолвера.

    Returns:
        Строковый ключ для cache backend.
    """
    # default=str превращает date/Decimal/UUID в строки — иначе json.dumps падает.
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    # sha256 вместо md5 — не вызывает вопросов на FIPS-системах.
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]
    return f'gql:{prefix}:{func_name}:{digest}'


def cache_metric[R](
    ttl: int = 300,
    prefix: str = 'gql',
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Декоратор для кеширования результата GraphQL-резолвера.

    Оборачивает синхронный резолвер и сохраняет результат в cache.
    При повторном вызове с теми же аргументами возвращает закешированное
    значение, не выполняя SQL-запрос.

    Пример:
        @strawberry.field
        @staff_only
        @cache_metric(ttl=300, prefix='orders')
        def order_metrics(self, info, date_from=None, date_to=None) -> OrderMetrics:
            ...

    Args:
        ttl: Время жизни кеша в секундах. По умолчанию 5 минут.
        prefix: Домен метрики. Разделяет ключи orders / products / users —
            удобно при ручной инвалидации.

    Returns:
        Декоратор, оборачивающий резолвер.
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(self: Any, info: Any, *args: Any, **kwargs: Any) -> R:
            key = _make_key(prefix, func.__name__, kwargs)

            try:
                cached_value: R | None = cache.get(key)
            except Exception:
                logger.exception('Cache GET failed: %s', key)
                cached_value = None

            if cached_value is not None:
                logger.debug('Cache HIT: %s', key)
                return cached_value

            logger.debug('Cache MISS: %s', key)
            result = func(self, info, *args, **kwargs)

            try:
                cache.set(key, result, ttl)
            except Exception:
                logger.exception('Cache SET failed: %s', key)

            return result

        return wrapper

    return decorator
