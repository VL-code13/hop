"""
Формы оформления заказов интернет-магазина.

Реализует валидацию контактных данных и адреса доставки по разделу 3.4 ТЗ.
"""

import re

from django import forms
from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r'^(\+7|7|8)?[\s\-]?$?[3-9][0-9]{2}$?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$',
    message="Введите корректный номер телефона (например, +7 (999) 123-45-67 или 89991234567)."
)


class OrderCreateForm(forms.Form):
    """Форма сбора контактных данных и адреса при чекауте."""

    full_name = forms.CharField(
        max_length=150,
        label='ФИО получателя',
        widget=forms.TextInput(attrs={
            'class': 'Input',
            'placeholder': 'Иван Иванов',
            'id': 'id_full_name',
            'required': True,
        }),
    )
    phone = forms.CharField(
        max_length=25,
        label='Номер телефона',
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'Input',
            'placeholder': '+7 (999) 000-00-00',
            'id': 'id_phone',
            'required': True,
        }),
    )
    shipping_address = forms.CharField(
        label='Адрес доставки',
        widget=forms.Textarea(attrs={
            'class': 'Textarea',
            'placeholder': 'Город, улица, дом, квартира / офис, индекс',
            'id': 'id_shipping_address',
            'rows': 3,
            'required': True,
        }),
    )
    payment_method = forms.ChoiceField(
        choices=[
            ('card', 'Банковская карта онлайн'),
            ('wallet', 'СБП / Электронный кошелек'),
            ('cash', 'Оплата при получении курьеру'),
        ],
        initial='card',
        widget=forms.RadioSelect,
        required=False,
    )

    def clean_phone(self) -> str:
        """Нормализация номера телефона с удалением нецифровых символов."""
        phone: str = self.cleaned_data.get('phone', '')
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) not in (10, 11):
            raise forms.ValidationError('Номер телефона должен содержать 10 или 11 цифр.')
        return phone
