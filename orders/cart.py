"""
Сервисный слой сессионной корзины товаров.

Реализует требования раздела 3.3 ТЗ («Корзина (/cart/): хранение в сессии,
подсчет стоимости, учет остатка, проверка наличия»).
"""

from decimal import Decimal
from typing import Any, Generator
from django.conf import settings
from django.http import HttpRequest
from products.models import Product

CART_SESSION_ID: str = getattr(settings, 'CART_SESSION_ID', 'cart')


class Cart:
    """Управление корзиной покупок в текущей сессии пользователя."""

    def __init__(self, request: HttpRequest) -> None:
        """Инициализирует корзину из сессии текущего запроса."""
        self.session = request.session
        cart: dict[str, dict[str, Any]] = self.session.get(CART_SESSION_ID)  # type: ignore[assignment]
        if not cart:
            cart = self.session[CART_SESSION_ID] = {}
        self.cart: dict[str, dict[str, Any]] = cart

    def add(self, product: Product, quantity: int = 1, override_quantity: bool = False) -> None:
        """
        Добавляет товар в корзину или обновляет количество с ограничением по складу.
        """
        product_id: str = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {
                'quantity': 0,
                'price': str(product.price),
            }

        if override_quantity:
            new_quantity = quantity
        else:
            new_quantity = self.cart[product_id]['quantity'] + quantity

        # Бизнес-правило: нельзя добавить больше фактического наличия (раздел 3.3 ТЗ)
        self.cart[product_id]['quantity'] = max(1, min(new_quantity, product.stock))
        self.save()

    def remove(self, product: Product) -> None:
        """Удаляет указанный товар из корзины."""
        product_id: str = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self) -> None:
        """Помечает сессию как измененную для гарантированного сохранения в хранилище."""
        self.session.modified = True

    def clear(self) -> None:
        """Очищает данные корзины в текущей сессии."""
        if CART_SESSION_ID in self.session:
            del self.session[CART_SESSION_ID]
            self.save()

    def __iter__(self) -> Generator[dict[str, Any], None, None]:
        """
        Итерирует позиции корзины, подтягивая актуальные экземпляры Product из БД.
        Предотвращает показ устаревших цен.
        """
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        cart_copy = self.cart.copy()

        for product in products:
            cart_copy[str(product.id)]['product'] = product

        for item in cart_copy.values():
            if 'product' in item:
                item['price'] = Decimal(item['price'])
                item['total_price'] = item['price'] * item['quantity']
                yield item

    def __len__(self) -> int:
        """Считает суммарное количество штук всех товаров в корзине."""
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self) -> Decimal:
        """Вычисляет общую денежную стоимость корзины."""
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())
