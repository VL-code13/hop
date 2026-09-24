"""Тесты кеширования аналитических метрик GraphQL.

Проверяют две вещи:

1. Повторный запрос с теми же параметрами возвращает закешированный
   результат — без повторного SQL-запроса (метрика «устаревает» до TTL).
2. Права проверяются ДО кеша — обычный пользователь не получит данные
   из кеша в обход @staff_only.

Фикстура _clear_cache живёт в conftest.py с autouse=True — она сбрасывает
кеш перед каждым тестом проекта. Здесь её дублировать не нужно.
"""

import pytest
from django.core.cache import cache
from django.test import Client


@pytest.mark.django_db
def test_order_metrics_cached_between_requests(
    staff_token: str,
    order_factory,
) -> None:
    """Повторный запрос с теми же параметрами возвращает закешированный результат.

    Сценарий:
        1. Создаём 1 оплаченный заказ, дёргаем orderMetrics — MISS, count=1.
        2. Создаём второй заказ (БД теперь содержит 2).
        3. Повторяем тот же GraphQL-запрос — HIT, всё ещё count=1
           (доказывает, что данные пришли из кеша, а не из БД).
        4. Сбрасываем кеш вручную.
        5. Третий запрос — MISS, count=2 (актуальные данные).
    """
    order_factory(status='paid')

    client = Client()
    url = '/graphql/'
    query = '{"query": "{ orderMetrics { orderCount } }"}'
    auth = f'Bearer {staff_token}'

    # 1. MISS — идёт в БД, кеширует результат.
    first = client.post(
        url,
        data=query,
        content_type='application/json',
        HTTP_AUTHORIZATION=auth,
    )
    assert first.json()['data']['orderMetrics']['orderCount'] == 1

    # 2. Создаём ещё один заказ. В БД теперь 2, но кеш об этом не знает.
    order_factory(status='paid')

    # 3. HIT — возвращает старое значение из кеша (1, не 2).
    second = client.post(
        url,
        data=query,
        content_type='application/json',
        HTTP_AUTHORIZATION=auth,
    )
    assert second.json()['data']['orderMetrics']['orderCount'] == 1

    # 4. Сбрасываем кеш — следующий запрос пойдёт в БД.
    cache.clear()

    # 5. MISS — видим актуальные данные.
    third = client.post(
        url,
        data=query,
        content_type='application/json',
        HTTP_AUTHORIZATION=auth,
    )
    assert third.json()['data']['orderMetrics']['orderCount'] == 2


@pytest.mark.django_db
def test_permissions_checked_before_cache(
    staff_token: str,
    user_token: str,
    order_factory,
) -> None:
    """Права проверяются ДО кеша — обычный пользователь не обойдёт @staff_only.

    Порядок декораторов в резолвере критичен:

        @strawberry.field
        @staff_only          # ← СНАРУЖИ, выполняется первым
        @cache_metric(...)   # ← ВНУТРИ, только после проверки прав
        def order_metrics(...): ...

    Если поменять @staff_only и @cache_metric местами, обычный
    пользователь получит закешированные данные в обход проверки.

    Сценарий:
        1. Staff дёргает orderMetrics — прогревает кеш.
        2. Обычный пользователь дёргает тот же запрос.
        3. Ожидаем FORBIDDEN, а не данные из кеша.
    """
    order_factory(status='paid')

    client = Client()
    query = '{"query": "{ orderMetrics { orderCount } }"}'

    # 1. Прогреваем кеш staff-запросом.
    warmup = client.post(
        '/graphql/',
        data=query,
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {staff_token}',
    )
    assert 'errors' not in warmup.json(), 'Прогрев кеша не должен падать'
    assert warmup.json()['data']['orderMetrics']['orderCount'] == 1

    # 2. Обычный пользователь с тем же запросом.
    response = client.post(
        '/graphql/',
        data=query,
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {user_token}',
    )
    payload = response.json()

    # 3. Ожидаем FORBIDDEN, а не данные из кеша.
    # GraphQL может вернуть data=None целиком (non-nullable поле упало),
    # либо data={'orderMetrics': None}. Проверяем оба варианта.
    assert payload.get('data') is None or payload['data'].get('orderMetrics') is None
    assert payload['errors'][0]['extensions']['code'] == 'FORBIDDEN'
