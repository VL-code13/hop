"""
Модульные тесты приложения users.

Реализует проверку бизнес-требований по разделам 3.5, 3.7, 4 и 6.3 ТЗ:
- Аутентификация по Email или Username;
- Автоматическое создание Profile при регистрации;
- Обновление контактов и смена пароля в личном кабинете;
- Мягкое удаление учетной записи (Soft Delete);
- Получение и обновление JWT-токенов через REST API;
- Нормализация телефонов (`users.phone`).
"""

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order
from users.models import Profile
from users.phone import format_phone, normalize_phone

User = get_user_model()


# ──────────────────────── Web: аутентификация и профиль ────────────────────────


class UserAuthenticationAndProfileTestCase(TestCase):
    """Тестирование аутентификации, регистрации и профилей в веб-интерфейсе."""

    def setUp(self) -> None:
        """Инициализация тестовых данных."""
        self.user = User.objects.create_user(
            username='brewmaster',
            email='brewmaster@hopbarley.ru',
            password='Password123!',
            first_name='Алексей',
            last_name='Смирнов',
        )

    def test_profile_auto_created_on_user_creation(self) -> None:
        """Проверка автоматического создания связанного объекта Profile (сигнал post_save)."""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, Profile)

    def test_login_by_username(self) -> None:
        """Успешный вход в систему по имени пользователя (username)."""
        login_success = self.client.login(username='brewmaster', password='Password123!')
        self.assertTrue(login_success)

    def test_login_by_email(self) -> None:
        """Успешный вход в систему по адресу электронной почты (email)."""
        login_success = self.client.login(username='brewmaster@hopbarley.ru', password='Password123!')
        self.assertTrue(login_success)

    def test_login_with_invalid_credentials(self) -> None:
        """Попытка входа с неверным паролем отклоняется."""
        login_success = self.client.login(username='brewmaster@hopbarley.ru', password='WrongPassword')
        self.assertFalse(login_success)

    def test_user_registration_creates_account_and_profile(self) -> None:
        """Регистрация нового пользователя через веб-форму."""
        payload = {
            'email': 'newbrewer@hopbarley.ru',
            'password1': 'StrongBeerPass2026!',
            'password2': 'StrongBeerPass2026!',
        }
        response = self.client.post(reverse('users:register'), data=payload)
        self.assertRedirects(response, reverse('users:account'))

        new_user = User.objects.filter(email='newbrewer@hopbarley.ru').first()
        self.assertIsNotNone(new_user)
        assert new_user is not None
        self.assertTrue(new_user.is_active)
        self.assertTrue(Profile.objects.filter(user=new_user).exists())

    def test_registration_rejects_weak_password(self) -> None:
        """Регистрация с паролем «123» отклоняется (AUTH_PASSWORD_VALIDATORS)."""
        payload = {
            'email': 'weakpass@hopbarley.ru',
            'password1': '123',
            'password2': '123',
        }
        response = self.client.post(reverse('users:register'), data=payload)
        # Регистрация не прошла — пользователь не создан
        self.assertFalse(User.objects.filter(email='weakpass@hopbarley.ru').exists())
        # Страница отрисована с ошибками (200, не редирект)
        self.assertEqual(response.status_code, 200)

    def test_account_page_access_restricted_for_anonymous_user(self) -> None:
        """Анонимный пользователь при попытке входа в ЛК перенаправляется на форму логина."""
        response = self.client.get(reverse('users:account'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response.url)  # type: ignore

    def test_update_profile_contact_data(self) -> None:
        """Обновление контактов и адреса доставки в личном кабинете.

        Телефон нормализуется в ``+7XXXXXXXXXX`` на уровне формы.
        """
        self.client.login(username='brewmaster', password='Password123!')

        payload: dict[str, Any] = {
            'action': 'update_profile',
            'first_name': 'Алексей',
            'last_name': 'Петров',
            'email': 'brewmaster_updated@hopbarley.ru',
            'phone': '+7 (999) 111-22-33',
            'default_shipping_address': 'г. Москва, ул. Пивоваров, д. 10, кв. 5',
        }
        response = self.client.post(reverse('users:account'), data=payload)
        self.assertRedirects(response, reverse('users:account'))

        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'Петров')
        self.assertEqual(self.user.email, 'brewmaster_updated@hopbarley.ru')
        self.assertEqual(self.user.profile.phone, '+79991112233')  # нормализованный
        self.assertEqual(
            self.user.profile.default_shipping_address,
            'г. Москва, ул. Пивоваров, д. 10, кв. 5',
        )

    def test_change_password_in_account(self) -> None:
        """Смена пароля в личном кабинете с валидацией старого пароля."""
        self.client.login(username='brewmaster', password='Password123!')

        payload: dict[str, Any] = {
            'action': 'change_password',
            'old_password': 'Password123!',
            'new_password1': 'BrandNewPassword2026!',
            'new_password2': 'BrandNewPassword2026!',
        }
        response = self.client.post(reverse('users:account'), data=payload)
        self.assertRedirects(response, reverse('users:account'))

        self.client.logout()
        login_with_new_pass = self.client.login(username='brewmaster', password='BrandNewPassword2026!')
        self.assertTrue(login_with_new_pass)


# ──────────────────────── Soft Delete ────────────────────────


class UserSoftDeleteTestCase(TestCase):
    """Тестирование мягкого удаления аккаунта (Soft Delete) по разделу 3.5 ТЗ."""

    def setUp(self) -> None:
        """Создание пользователя и заказа для проверки финансовой истории."""
        self.user = User.objects.create_user(
            username='retiring_brewer',
            email='retiring@hopbarley.ru',
            password='Password123!',
        )
        self.order = Order.objects.create(
            user=self.user,
            total_price=Decimal('1500.00'),
            shipping_address='г. Санкт-Петербург, Невский пр-т, 1',
            status=Order.Status.DELIVERED,
        )

    def test_soft_delete_deactivates_user_and_preserves_orders(self) -> None:
        """Деактивация пользователя отключает вход, но сохраняет оформленные заказы."""
        self.client.login(username='retiring@hopbarley.ru', password='Password123!')

        response = self.client.post(reverse('users:delete_account'))
        self.assertRedirects(response, reverse('products:product_list'))

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        login_attempt = self.client.login(username='retiring@hopbarley.ru', password='Password123!')
        self.assertFalse(login_attempt)

        self.assertTrue(Order.objects.filter(id=self.order.id, user=self.user).exists())


# ──────────────────────── JWT API ────────────────────────


class UserJWTAPITestCase(TestCase):
    """Тестирование выпуска и обновления JWT-токенов через REST API (раздел 3.7 ТЗ)."""

    def setUp(self) -> None:
        """Инициализация API-клиента и тестового пользователя."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='api_brewer',
            email='api_brewer@hopbarley.ru',
            password='ApiPassword123!',
        )

    def test_obtain_token_pair_by_username(self) -> None:
        """Получение пары access и refresh токенов по username."""
        payload = {
            'username': 'api_brewer',
            'password': 'ApiPassword123!',
        }
        response = self.client.post(reverse('token_obtain_pair'), data=payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)  # type: ignore
        self.assertIn('refresh', response.data)  # type: ignore

    def test_obtain_token_pair_by_email(self) -> None:
        """Получение JWT-токенов по email (EmailOrUsernameModelBackend)."""
        payload = {
            'username': 'api_brewer@hopbarley.ru',
            'password': 'ApiPassword123!',
        }
        response = self.client.post(reverse('token_obtain_pair'), data=payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)  # type: ignore
        self.assertIn('refresh', response.data)  # type: ignore

    def test_refresh_jwt_token(self) -> None:
        """Обновление access-токена с помощью refresh-токена."""
        obtain_response = self.client.post(
            reverse('token_obtain_pair'),
            data={'username': 'api_brewer', 'password': 'ApiPassword123!'},
        )
        refresh_token = obtain_response.data['refresh']  # type: ignore

        refresh_response = self.client.post(
            reverse('token_refresh'),
            data={'refresh': refresh_token},
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)  # type: ignore


# ──────────────────────── Утилиты телефона (pytest-style) ────────────────────────
#
# Ниже — обычные pytest-функции, не unittest.TestCase.
# Это позволяет использовать @pytest.mark.parametrize, недоступный на методах
# TestCase. БД не используется — тесты работают без фикстуры db и без Django-клиента.


class TestNormalizePhone:
    """Проверки ``normalize_phone`` на всех поддерживаемых форматах ввода."""

    @pytest.mark.parametrize(
        ('raw', 'expected'),
        [
            ('+7 (999) 111-22-33', '+79991112233'),
            ('+79991112233', '+79991112233'),
            ('89991112233', '+79991112233'),
            ('7 999 111 22 33', '+79991112233'),
            ('9991112233', '+79991112233'),
            ('', ''),  # пусто → пусто
            ('   ', ''),  # только пробелы → пусто
        ],
    )
    def test_valid_inputs(self, raw: str, expected: str) -> None:
        """Корректные форматы нормализуются к ``+7XXXXXXXXXX``."""
        assert normalize_phone(raw) == expected

    @pytest.mark.parametrize(
        'raw',
        [
            '123',  # слишком короткий
            '123456789012',  # 12 цифр
            '99991234567',  # 11 цифр, первая не 7/8
            '12345678901234',  # 14 цифр
        ],
    )
    def test_invalid_inputs(self, raw: str) -> None:
        """Некорректные длины и первая цифра → ``ValueError``."""
        with pytest.raises(ValueError):
            normalize_phone(raw)


class TestFormatPhone:
    """Проверки ``format_phone`` для отображения в шаблонах."""

    def test_normalized_to_display(self) -> None:
        """Стандартный формат ``+7XXXXXXXXXX`` → ``+7 (XXX) XXX-XX-XX``."""
        assert format_phone('+79991112233') == '+7 (999) 111-22-33'

    def test_garbage_passes_through(self) -> None:
        """Нераспознанная строка возвращается как есть, без исключения."""
        assert format_phone('garbage') == 'garbage'
        assert format_phone('') == ''

    def test_already_formatted_still_works(self) -> None:
        """Если уже отформатировано, функция не должна ломаться (pass-through)."""
        # +7 (999) 111-22-33 → не матчит ^\+7\d{10}$, возвращается как есть
        assert format_phone('+7 (999) 111-22-33') == '+7 (999) 111-22-33'
