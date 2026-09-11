"""Формы пользовательского интерфейса для работы с товарами."""

from typing import Any
from django import forms


class AddToCartProductForm(forms.Form):
    """Форма выбора количества товара при добавлении в корзину.
    Валидирует минимальное и максимальное доступное число штук
    с учетом реального остатка на складе.
    """

    quantity: forms.IntegerField = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            "class": "quantity-input",
            "min": "1",
            "step": "1",
        }),
        label="Количество",
    )

    def __init__(self, *args: Any, max_stock: int = 99, **kwargs: Any) -> None:
        """Инициализирует форму, ограничивая ввод максимальным доступным остатком."""
        super().__init__(*args, **kwargs)
        if max_stock > 0:
            self.fields["quantity"].widget.attrs["max"] = str(max_stock)
            self.fields["quantity"].max_value = max_stock
