"""
Сервисный слой сессионной корзины товаров.

Реализует требования раздела 3.3 ТЗ («Корзина (/cart/): хранение в сессии,
подсчет стоимости, учет остатка, проверка наличия»).
"""

import copy
from collections.abc import Generator
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.http import HttpRequest

from products.models import Product

CART_SESSION_ID: str = getattr(settings, 'CART_SESSION_ID', 'cart')


class Cart:
    """Управление корзиной покупок в текущей сессии пользователя."""

    def __init__(self, request: HttpRequest) -> None:
        self.session = request.session
        cart: dict[str, dict[str, Any]] = self.session.get(CART_SESSION_ID) or {}
        if not cart:
            cart = self.session[CART_SESSION_ID] = {}
        self.cart: dict[str, dict[str, Any]] = cart

    def add(self, product: Product, quantity: int = 1, override_quantity: bool = False) -> None:
        """
        Добавляет товар в корзину или обновляет количество с ограничением по складу.

        Бизнес-правила (раздел 3.3 ТЗ):
        - Нельзя добавить товар с нулевым остатком.
        - Нельзя добавить больше, чем есть на складе.
        - quantity <= 0 при override_quantity удаляет позицию из корзины.
        """
        product_id: str = str(product.id)

        if product.stock <= 0:
            return

        # Сначала убеждаемся, что запись существует — потом считаем
        if product_id not in self.cart:
            self.cart[product_id] = {
                'quantity': 0,
                'price': str(product.price),
            }

        if override_quantity:
            if quantity <= 0:
                del self.cart[product_id]
                self.save()
                return
            new_quantity = quantity
        else:
            new_quantity = self.cart[product_id]['quantity'] + quantity

        self.cart[product_id]['quantity'] = min(new_quantity, product.stock)
        self.save()

    def remove(self, product: Product) -> None:
        product_id: str = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self) -> None:
        self.session.modified = True

    def clear(self) -> None:
        if CART_SESSION_ID in self.session:
            del self.session[CART_SESSION_ID]
            self.save()

    def __iter__(self) -> Generator[dict[str, Any], None, None]:
        """
        Итерирует позиции корзины, подтягивая актуальные экземпляры Product из БД.

        Использует copy.deepcopy для изоляции от сессионных данных:
        shallow copy разделял внутренние dict-и, и объекты Product
        утекали в session['cart'], повреждая сериализацию сессии.
        """
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        cart_copy = copy.deepcopy(self.cart)

        for product in products:
            cart_copy[str(product.id)]['product'] = product

        for item in cart_copy.values():
            if 'product' in item:
                item['price'] = Decimal(item['price'])
                item['total_price'] = item['price'] * item['quantity']
                yield item

    def __len__(self) -> int:
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self) -> Decimal:
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())
