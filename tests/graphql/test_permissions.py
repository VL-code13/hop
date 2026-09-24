"""Тесты прав доступа к GraphQL-эндпоинту."""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_is_public() -> None:
    """Health-запрос работает без токена."""
    response = Client().post(
        '/graphql/',
        data='{"query": "{ health }"}',
        content_type='application/json',
    )
    assert response.status_code == 200
    assert response.json()['data']['health'] == 'ok'


@pytest.mark.django_db
def test_analytics_requires_auth() -> None:
    """Без токена — UNAUTHENTICATED.

    GraphQL может вернуть «data: null» целиком (а не «data.orderMetrics: null»),
    если ошибка выброшена до построения поля в ответе. Поэтому проверяем
    через .get() и фокусируемся на коде ошибки.
    """
    response = Client().post(
        '/graphql/',
        data='{"query": "{ orderMetrics { totalRevenue } }"}',
        content_type='application/json',
    )
    payload = response.json()
    # data может быть None целиком, либо содержать orderMetrics=None.
    assert payload.get('data') is None or payload['data'].get('orderMetrics') is None
    assert payload['errors'][0]['extensions']['code'] == 'UNAUTHENTICATED'


@pytest.mark.django_db
def test_analytics_forbidden_for_regular_user(user_token: str) -> None:
    """Обычный покупатель получает FORBIDDEN, а не данные."""
    response = Client().post(
        '/graphql/',
        data='{"query": "{ orderMetrics { totalRevenue } }"}',
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {user_token}',
    )
    payload = response.json()
    assert payload.get('data') is None or payload['data'].get('orderMetrics') is None
    assert payload['errors'][0]['extensions']['code'] == 'FORBIDDEN'


@pytest.mark.django_db
def test_analytics_available_for_staff(staff_token: str) -> None:
    """Staff-пользователь получает данные аналитики."""
    response = Client().post(
        '/graphql/',
        data='{"query": "{ orderMetrics { totalRevenue orderCount } }"}',
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {staff_token}',
    )
    payload = response.json()
    assert 'errors' not in payload
    assert payload['data']['orderMetrics']['orderCount'] == 0
