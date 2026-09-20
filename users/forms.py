"""
Формы аутентификации, регистрации и редактирования профиля пользователей.

Реализует требования разделов 3.5 и 3.7 ТЗ интернет-магазина Hop & Barley.
"""

from __future__ import annotations

import re
from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
)
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Profile

User = get_user_model()

phone_validator = RegexValidator(
    regex=r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$',
    message="Введите корректный номер телефона (например, +7 (999) 123-45-67 или 89991234567)."
)


class UserLoginForm(AuthenticationForm):
    """Форма авторизации с поддержкой входа по Email или Username."""

    username = forms.CharField(
        label='Email или имя пользователя',
        widget=forms.TextInput(attrs={
            'class': 'Input',
            'placeholder': 'brewer@hopbarley.ru',
            'id': 'id_username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'Input',
            'placeholder': '••••••••',
            'id': 'id_password',
        })
    )


class UserRegisterForm(forms.ModelForm):
    """
    Форма регистрации нового пользователя.
    При обнаружении деактивированного аккаунта предлагает сброс пароля для реактивации.
    """

    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'Input',
            'placeholder': 'brewer@hopbarley.ru',
            'required': True,
        })
    )
    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'Input',
            'placeholder': '••••••••',
            'required': True,
        })
    )
    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={
            'class': 'Input',
            'placeholder': '••••••••',
            'required': True,
        })
    )

    class Meta:
        model = User
        fields = ('email',)

    def clean_email(self) -> str:
        email = self.cleaned_data.get('email', '').strip().lower()
        existing_user = User.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_active:
                raise ValidationError('Пользователь с таким email уже зарегистрирован.')

            reset_url = reverse('users:password_reset')
            message = mark_safe(
                f'Аккаунт с email <b>{email}</b> был ранее деактивирован. '
                f'Для восстановления доступа и сохранения истории заказов, пожалуйста, '
                f'<a href="{reset_url}?email={email}" style="color: #e8a84c; text-decoration: underline; font-weight: 600;">'
                f'восстановите пароль</a>.'
            )
            raise ValidationError(message)

        return email

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')

        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Введенные пароли не совпадают.')

        return cleaned_data

    def save(self, commit: bool = True) -> Any:
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
        email_field_name = User.get_email_field_name()
        return User._default_manager.filter(
            **{f'{email_field_name}__iexact': email}
        )


class ProfileUpdateForm(forms.ModelForm):
    """Форма редактирования личных и контактных данных в личном кабинете."""

    phone = forms.CharField(
        label='Номер телефона',
        required=False,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'Input',
            'placeholder': '+7 (999) 000-00-00',
            'id': 'id_phone',
        })
    )
    default_shipping_address = forms.CharField(
        label='Адрес доставки по умолчанию',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'Textarea',
            'placeholder': 'Город, улица, дом, квартира / офис',
            'rows': 3,
            'id': 'id_shipping_address',
        })
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
        phone = self.cleaned_data.get('phone', '').strip()
        if phone:
            digits_only = re.sub(r'\D', '', phone)
            if len(digits_only) not in (10, 11):
                raise ValidationError('Номер телефона должен содержать 10 или 11 цифр.')
        return phone

    def save(self, commit: bool = True) -> Any:
        user = super().save(commit=commit)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = self.cleaned_data.get('phone', '')
        profile.default_shipping_address = self.cleaned_data.get('default_shipping_address', '')
        if commit:
            profile.save()
        return user


class PasswordChangeCustomForm(PasswordChangeForm):
    """Кастомная форма смены пароля с классами оформления."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'Input'})
