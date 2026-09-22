"""Формы оформления заказов интернет-магазина.

Реализует валидацию контактных данных и адреса доставки по разделу 3.4 ТЗ.
"""

from django import forms

from users.phone import normalize_phone, phone_validator


class OrderCreateForm(forms.Form):
    """Форма сбора контактных данных и адреса при чекауте."""

    full_name = forms.CharField(
        max_length=150,
        label='ФИО получателя',
        widget=forms.TextInput(
            attrs={
                'class': 'Input',
                'placeholder': 'Иван Иванов',
                'id': 'id_full_name',
                'required': True,
            }
        ),
    )
    phone = forms.CharField(
        max_length=25,
        label='Номер телефона',
        validators=[phone_validator],
        widget=forms.TextInput(
            attrs={
                'class': 'Input',
                'placeholder': '+7 (999) 000-00-00',
                'id': 'id_phone',
                'required': True,
            }
        ),
    )
    shipping_address = forms.CharField(
        label='Адрес доставки',
        widget=forms.Textarea(
            attrs={
                'class': 'Textarea',
                'placeholder': 'Город, улица, дом, квартира / офис, индекс',
                'id': 'id_shipping_address',
                'rows': 3,
                'required': True,
            }
        ),
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
        """Валидирует и нормализует телефон к формату ``+7XXXXXXXXXX``.

        Это гарантирует, что в поле ``Order.shipping_address`` попадёт
        номер в едином формате — удобно для курьера и поиска.
        """
        phone: str = self.cleaned_data.get('phone', '').strip()
        if not phone:
            return ''
        try:
            return normalize_phone(phone)
        except ValueError as err:
            raise forms.ValidationError(str(err)) from err
