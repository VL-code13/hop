"""
Сериализаторы REST API для приложения users.
Реализует требования раздела 3.7 ТЗ (REST API: регистрация через JWT).
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.utils.html import format_html
from rest_framework import serializers

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Сериализатор регистрации пользователя через REST API.

    Повторяет логику UserRegisterForm:
        - проверка уникальности email (с предложением реактивации);
        - валидация пароля через AUTH_PASSWORD_VALIDATORS;
        - проверка совпадения password1 / password2;
        - генерация уникального username из email.

    Возвращает: id, email, username (write_only пароли).
    Токены генерируются во view — это разделение ответственности.
    """

    email = serializers.EmailField(required=True)
    password1 = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )
    password2 = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'password1', 'password2')
        read_only_fields = ('id', 'username')

    def validate_email(self, value: str) -> str:
        """
        Валидирует email и, при необходимости, предлагает реактивацию аккаунта.

        Использует format_html вместо mark_safe — аргументы экранируются
        автоматически, что исключает XSS через email.
        """
        email = value.strip().lower()
        existing_user = User.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_active:
                raise serializers.ValidationError('Пользователь с таким email уже зарегистрирован.')
            reset_url = reverse('users:password_reset')
            message = format_html(
                'Аккаунт с email {} был ранее деактивирован. '
                'Для восстановления доступа и сохранения истории заказов, '
                "пожалуйста, <a href='{}'>восстановите пароль</a>.",
                email,
                reset_url,
            )
            raise serializers.ValidationError(message)

        return email

    def validate_password1(self, value: str) -> str:
        """
        Прогоняет пароль через AUTH_PASSWORD_VALIDATORS из settings.

        Создаём «фантомного» пользователя с email, чтобы
        UserAttributeSimilarityValidator мог сравнить пароль с email.
        """
        email = self.initial_data.get('email', '')
        user = User(email=email)
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Проверяет совпадение пароля и его подтверждения."""
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError({'password2': 'Введенные пароли не совпадают.'})
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Any:
        """
        Создаёт пользователя с уникальным username, сгенерированным из email.
        """
        validated_data.pop('password2')
        password = validated_data.pop('password1')
        email = validated_data['email']

        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}{counter}'
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
        return user
