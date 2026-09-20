"""Формы пользовательского интерфейса для работы с товарами."""

from typing import Any

from django import forms


class AddToCartProductForm(forms.Form):
    """Форма выбора количества товара при добавлении в корзину.

    Валидирует верхнюю границу ввода исходя из фактического
    наличия товара на складе (stock) по разделу 3.2 и 3.3 ТЗ.
    """

    # Аннотация типа убрана: django-stubs считает, что аннотация
    # делает поле инстанс-переменной, а не класс-переменной Form.
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            "class": "search-input",
            "min": "1",
            "step": "1",
            "id": "id_quantity",
            'style': 'width: 70px; padding: 8px; text-align: center;',
        }),
        label="Количество",
    )

    def __init__(self, *args: Any, max_stock: int = 99, **kwargs: Any) -> None:
        """
        Инициализирует форму, ограничивая ввод максимальным доступным остатком.

        Если товар на складе присутствует, атрибут max в HTML-виджете
        и max_value валидатора ограничиваются этим числом.

        self.fields["quantity"] типизирован django-stubs как Field (базовый класс),
        но фактически это IntegerField, у которого есть max_value.
        # type: ignore[attr-defined] заглушает ошибку — в рантайме всё работает.
        """
        super().__init__(*args, **kwargs)
        if max_stock > 0:
            self.fields["quantity"].widget.attrs["max"] = str(max_stock)
            self.fields["quantity"].max_value = max_stock  # type: ignore[attr-defined]
