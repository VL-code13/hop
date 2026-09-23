import pytest
from django.test import Client


@pytest.mark.django_db
def test_me_returns_authenticated_user(user_token: str, user) -> None:
    """`me` возвращает профиль текущего пользователя."""
    response = Client().post(
        '/graphql/',
        data='{"query": "{ me { id username email } }"}',
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {user_token}',
    )
    me = response.json()['data']['me']
    assert me['username'] == user.username


@pytest.mark.django_db
def test_me_returns_null_for_anonymous() -> None:
    """Без токена `me` возвращает null, а не ошибку."""
    response = Client().post(
        '/graphql/',
        data='{"query": "{ me { id } }"}',
        content_type='application/json',
    )
    payload = response.json()
    assert payload['data']['me'] is None
    assert 'errors' not in payload
