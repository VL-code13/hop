"""Формы оформления заказа и взаимодействия с корзиной."""

from django import forms
from .models import Order


class OrderCreateForm(forms.ModelForm):
    """Форма ввода адреса и способа оплаты при оформлении заказа."""

    class Meta:
        model = Order
        fields = ('shipping_address', 'payment_method')
        widgets = {
            'shipping_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Укажите город, улицу, дом, квартиру и почтовый индекс',
                'required': True,
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control',
            }),
        }


class CartAddProductForm(forms.Form):
    """Форма добавления товара с детальной страницы или каталога."""

    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'quantity-input', 'min': '1'}),
        label="Количество",
    )
    override = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput,
    )