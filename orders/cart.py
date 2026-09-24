"""
Сервисный слой сессионной корзины товаров.

Реализует требования разделов 3.3 и 6.3 ТЗ («Корзина: хранение в сессии,
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
    """Управление корзиной покупок в сессии текущего пользователя."""

    def __init__(self, request: HttpRequest) -> None:
        """Инициализирует корзину из сессионных данных запроса."""
        self.session = request.session
        cart: dict[str, dict[str, Any]] = self.session.get(CART_SESSION_ID) or {}
        if not cart:
            cart = self.session[CART_SESSION_ID] = {}
        self.cart: dict[str, dict[str, Any]] = cart

    def add(self, product: Product, quantity: int = 1, override_quantity: bool = False) -> bool:
        """
        Добавляет товар в корзину или обновляет количество с контролем остатка.

        Возвращает:
            True — если количество успешно зафиксировано;
            False — если запрашиваемое количество превышает остаток на складе.
        """
        product_id: str = str(product.id)

        # 1. Проверяем физическое наличие на складе
        if product.stock <= 0:
            return False

        current_quantity: int = self.cart.get(product_id, {}).get('quantity', 0)

        # 2. Вычисляем итоговое целевое количество
        if override_quantity:
            if quantity <= 0:
                self.remove(product)
                return True
            target_quantity = quantity
        else:
            target_quantity = current_quantity + quantity

        # 3. Жесткая валидация: не срезаем остаток тихо, а отклоняем операцию
        if target_quantity > product.stock:
            return False

        # 4. Фиксируем актуальную стоимость и количество
        self.cart[product_id] = {
            'quantity': target_quantity,
            'price': str(product.price),
        }
        self.save()
        return True

    def remove(self, product: Product) -> None:
        """Удаляет позицию из сессионной корзины."""
        product_id: str = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self) -> None:
        """Помечает сессию флагом modified для сохранения в сессионное хранилище."""
        self.session.modified = True

    def clear(self) -> None:
        """Полная очистка корзины из сессии."""
        if CART_SESSION_ID in self.session:
            del self.session[CART_SESSION_ID]
            self.save()

    def __iter__(self) -> Generator[dict[str, Any], None, None]:
        """
        Генератор для итерации по элементам корзины.
        Изолирует Product через deepcopy, исключая порчу сессионных данных.
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
        """Возвращает суммарное количество всех штук товаров в корзине."""
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self) -> Decimal:
        """Вычисляет общую стоимость всех позиций."""
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())
