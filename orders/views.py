"""
Контроллеры корзины и оформления заказов.

Реализует требования разделов 3.3 и 3.4 ТЗ.
"""

from decimal import Decimal
from typing import Any
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import View

from products.models import Product
from .cart import Cart
from .forms import OrderCreateForm
from .models import Order, OrderItem


class CartDetailView(View):
    """Отображение содержимого корзины."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        return render(request, 'cart_detail.html', {'cart': cart})


class CartAddView(View):
    """Добавление товара в сессионную корзину."""

    def post(self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id, is_active=True)

        if product.stock <= 0:
            messages.warning(request, f'Товар «{product.name}» временно отсутствует на складе.')
            return redirect('orders:cart_detail')

        try:
            quantity = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            quantity = 1

        cart.add(product=product, quantity=quantity)
        messages.success(request, f'Товар «{product.name}» добавлен в корзину.')
        return redirect('orders:cart_detail')


class CartUpdateView(View):
    """Обновление количества единиц товара в корзине."""

    def post(self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id, is_active=True)

        try:
            quantity = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            messages.error(request, 'Некорректное количество.')
            return redirect('orders:cart_detail')

        cart.add(product=product, quantity=quantity, override_quantity=True)
        return redirect('orders:cart_detail')


class CartRemoveView(View):
    """Удаление позиции из корзины."""

    def post(self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        cart.remove(product)
        messages.info(request, f'Товар «{product.name}» удален из корзины.')
        return redirect('orders:cart_detail')


class OrderCreateView(LoginRequiredMixin, View):
    """Создание заказа на основе сессионной корзины только для авторизованных пользователей."""

    login_url = reverse_lazy('users:login')

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        if len(cart) == 0:
            messages.warning(request, 'Ваша корзина пуста.')
            return redirect('products:product_list')

        initial_data: dict[str, Any] = {
            'full_name': request.user.get_full_name() or request.user.username,
        }
        if hasattr(request.user, 'profile'):
            initial_data['phone'] = request.user.profile.phone or ''
            initial_data['shipping_address'] = request.user.profile.default_shipping_address or ''

        form = OrderCreateForm(initial=initial_data)
        return render(request, 'checkout.html', {'cart': cart, 'form': form})

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        if len(cart) == 0:
            messages.warning(request, 'Ваша корзина пуста.')
            return redirect('products:product_list')

        form = OrderCreateForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name']
            phone = form.cleaned_data['phone']
            address = form.cleaned_data['shipping_address']
            full_shipping_info = f"{full_name}, Тел: {phone}\n{address}"
            payment_method = form.cleaned_data.get('payment_method', Order.PaymentMethod.CASH)

            # Проверка остатков перед оформлением
            for item in cart:
                product = item['product']
                if product.stock < item['quantity']:
                    messages.error(
                        request,
                        f'Товар «{product.name}» осталось {product.stock} шт. '
                        f'У вас в корзине {item["quantity"]} шт. Уменьшите количество.',
                    )
                    return redirect('orders:cart_detail')

            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    shipping_address=full_shipping_info,
                    total_price=Decimal(str(cart.get_total_price())),
                    status=Order.Status.PENDING,
                    payment_method=payment_method,
                )

                for item in cart:
                    product = item['product']
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        price=item['price'],
                        quantity=item['quantity'],
                    )
                    # Списание остатка
                    product.stock -= item['quantity']
                    product.save(update_fields=['stock'])

            cart.clear()
            messages.success(request, f'Заказ №{order.id} успешно оформлен!')
            return redirect('orders:order_success', order_id=order.id)

        return render(request, 'checkout.html', {'cart': cart, 'form': form})


class OrderSuccessView(LoginRequiredMixin, View):
    """Страница подтверждения успешно созданного заказа."""

    def get(self, request: HttpRequest, order_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        order = get_object_or_404(Order, id=order_id, user=request.user)
        return render(request, 'order_success.html', {'order': order})
