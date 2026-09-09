"""Контекстные процессоры приложения заказов."""

from django.http import HttpRequest
from .cart import Cart


def cart(request: HttpRequest) -> dict[str, Cart]:
    """Возвращает инициализированную корзину для контекста любого шаблона."""
    return {'cart': Cart(request)}