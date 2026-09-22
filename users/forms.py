"""Формы аутентификации, регистрации и редактирования профиля пользователей.

Реализует требования разделов 3.5 и 3.7 ТЗ интернет-магазина Hop & Barley.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html

from .models import Profile
from .phone import normalize_phone, phone_validator

User = get_user_model()


class UserLoginForm(AuthenticationForm):
    """Форма авторизации с поддержкой входа по Email или Username."""

    username = forms.CharField(
        label='Email или имя пользователя',
        widget=forms.TextInput(
            attrs={
                'class': 'Input',
                'placeholder': 'brewer@hopbarley.ru',
                'id': 'id_username',
                'autofocus': True,
            }
        ),
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(
            attrs={
                'class': 'Input',
                'placeholder': '••••••••',
                'id': 'id_password',
            }
        ),
    )


class UserRegisterForm(forms.ModelForm):
    """
    Форма регистрации нового пользователя.

    Выполняет:
    - валидацию email (уникальность, реактивация деактивированного аккаунта);
    - проверку пароля через ``AUTH_PASSWORD_VALIDATORS`` из настроек;
    - проверку совпадения password1 / password2;
    - генерацию уникального username из email.
    """

    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(
            attrs={
                'class': 'Input',
                'placeholder': 'brewer@hopbarley.ru',
                'required': True,
            }
        ),
    )
    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(
            attrs={
                'class': 'Input',
                'placeholder': '••••••••',
                'required': True,
            }
        ),
    )
    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(
            attrs={
                'class': 'Input',
                'placeholder': '••••••••',
                'required': True,
            }
        ),
    )

    class Meta:
        model = User
        fields = ('email',)

    def clean_email(self) -> str:
        """Валидирует email и, при необходимости, предлагает реактивацию аккаунта.

        Использует ``format_html`` вместо ``mark_safe`` — аргументы
        экранируются автоматически, что исключает XSS через email.
        """
        email = self.cleaned_data.get('email', '').strip().lower()
        existing_user = User.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_active:
                raise ValidationError('Пользователь с таким email уже зарегистрирован.')

            reset_url = reverse('users:password_reset')
            message = format_html(
                'Аккаунт с email <b>{}</b> был ранее деактивирован. '
                'Для восстановления доступа и сохранения истории заказов, пожалуйста, '
                '<a href="{}?email={}" '
                'style="color: #e8a84c; text-decoration: underline; font-weight: 600;">'
                'восстановите пароль</a>.',
                email,
                reset_url,
                email,
            )
            raise ValidationError(message)

        return email

    def clean_password1(self) -> str:
        """Прогоняет пароль через ``AUTH_PASSWORD_VALIDATORS`` из settings.

        Валидаторы включают:
        - ``UserAttributeSimilarityValidator`` — сравнение с email/username;
        - ``MinimumLengthValidator`` — минимум 8 символов;
        - ``CommonPasswordValidator`` — защита от топовых паролей;
        - ``NumericPasswordValidator`` — запрет пароля из цифр.

        Без этого вызова пароль ``123`` или ``password`` успешно регистрировался.
        """
        p1 = self.cleaned_data.get('password1', '')
        if p1:
            # Создаём «фантомного» пользователя с заполненным email, чтобы
            # UserAttributeSimilarityValidator мог сравнить пароль с email.
            # self.instance здесь ещё пустой — cleaned_data заполнится позже.
            email = self.cleaned_data.get('email', '')
            user = User(email=email)
            validate_password(p1, user=user)
        return p1

    def clean(self) -> dict[str, Any]:
        """Проверяет совпадение пароля и его подтверждения."""
        cleaned_data = super().clean() or {}
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')

        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Введенные пароли не совпадают.')

        return cleaned_data

    def save(self, commit: bool = True) -> Any:
        """Сохраняет пользователя с уникальным username, сгенерированным из email."""
        user = super().save(commit=False)
        email = self.cleaned_data['email']
        user.email = email

        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}{counter}'
            counter += 1
        user.username = username

        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class CustomPasswordResetForm(PasswordResetForm):
    """Форма сброса пароля, разрешающая отправку токена для деактивированных аккаунтов."""

    def get_users(self, email: str) -> Any:
        """Возвращает пользователей по email без фильтра по is_active.

        Это позволяет деактивированному пользователю запросить сброс пароля
        и реактивировать аккаунт через ``ReactivatePasswordResetConfirmView``.
        """
        email_field_name = User.get_email_field_name()
        return User._default_manager.filter(**{f'{email_field_name}__iexact': email})


class ProfileUpdateForm(forms.ModelForm):
    """Форма редактирования личных и контактных данных в личном кабинете."""

    phone = forms.CharField(
        label='Номер телефона',
        required=False,
        validators=[phone_validator],
        widget=forms.TextInput(
            attrs={
                'class': 'Input',
                'placeholder': '+7 (999) 000-00-00',
                'id': 'id_phone',
            }
        ),
    )
    default_shipping_address = forms.CharField(
        label='Адрес доставки по умолчанию',
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'Textarea',
                'placeholder': 'Город, улица, дом, квартира / офис',
                'rows': 3,
                'id': 'id_shipping_address',
            }
        ),
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'Input', 'placeholder': 'Иван'}),
            'last_name': forms.TextInput(attrs={'class': 'Input', 'placeholder': 'Иванов'}),
            'email': forms.EmailInput(attrs={'class': 'Input', 'placeholder': 'brewer@hopbarley.ru'}),
        }

    def clean_phone(self) -> str:
        """Валидирует и нормализует телефон к формату ``+7XXXXXXXXXX``.

        Пользователь может ввести номер в любой форме — ``+7 (999) ...``,
        ``8 999 ...``, ``9991234567``. В БД сохраняется единый формат,
        что упрощает поиск и сравнение. Для отображения используется
        ``format_phone()`` из ``users.phone``.
        """
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            return ''
        try:
            return normalize_phone(phone)
        except ValueError as err:
            raise ValidationError(str(err)) from err

    def save(self, commit: bool = True) -> Any:
        """Сохраняет пользователя и связанный с ним Profile."""
        user = super().save(commit=commit)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = self.cleaned_data.get('phone', '')
        profile.default_shipping_address = self.cleaned_data.get('default_shipping_address', '')
        if commit:
            profile.save()
        return user


class PasswordChangeCustomForm(PasswordChangeForm):
    """Кастомная форма смены пароля с классами оформления.

    Наследуется от ``PasswordChangeForm`` — Django автоматически применяет
    ``AUTH_PASSWORD_VALIDATORS`` к новому паролю.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'Input'})
