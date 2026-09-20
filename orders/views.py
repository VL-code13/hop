"""
Контроллеры корзины и оформления заказов веб-интерфейса.

Реализует требования разделов 3.3 (корзина) и 3.4 (оформление заказа) ТЗ:
- Корзина хранится в сессии;
- Оформление заказа доступно авторизованным покупателям (LoginRequiredMixin);
- Контроллер облегчен: создание заказа и валидация остатков делегированы в OrderCreateSerializer;
- Email-уведомления покупателю и администраторам магазина.
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import View

from products.models import Product

from .cart import Cart
from .forms import OrderCreateForm
from .models import Order
from .serializers import OrderCreateSerializer


class CartDetailView(View):
    """Отображение содержимого корзины (доступно анонимным покупателям)."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        return render(request, 'cart_detail.html', {'cart': cart})


class CartAddView(View):
    """Добавление товара в сессионную корзину с валидацией доступности."""

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

        # Вызываем метод add сервиса Cart, проверяющий лимиты склада
        if cart.add(product=product, quantity=quantity, override_quantity=False):
            messages.success(request, f'Товар «{product.name}» добавлен в корзину.')
        else:
            messages.error(
                request,
                f'Невозможно добавить {quantity} шт. На складе доступно всего {product.stock} шт.',
            )
        return redirect('orders:cart_detail')


class CartUpdateView(View):
    """Перезапись количества товара в корзине."""

    def post(self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id, is_active=True)

        try:
            quantity = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            messages.error(request, 'Некорректное количество.')
            return redirect('orders:cart_detail')

        if not cart.add(product=product, quantity=quantity, override_quantity=True):
            messages.error(request, f'Недостаточно товара на складе (доступно: {product.stock} шт.).')
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
    """
    Облегченный контроллер чекаута:
    Валидация формы выполняется стандартной Django Form,
    а бизнес-логика проверки остатков, создания позиций и списания склада
    полностью делегирована в OrderCreateSerializer.
    """

    login_url = reverse_lazy('users:login')

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user: Any = request.user
        cart = Cart(request)
        if len(cart) == 0:
            messages.warning(request, 'Ваша корзина пуста.')
            return redirect('products:product_list')

        # Автозаполнение формы контактными данными из профиля пользователя
        initial_data: dict[str, Any] = {
            'full_name': user.get_full_name() or user.username,
        }
        if hasattr(user, 'profile'):
            initial_data['phone'] = user.profile.phone or ''
            initial_data['shipping_address'] = user.profile.default_shipping_address or ''

        form = OrderCreateForm(initial=initial_data)
        return render(request, 'checkout.html', {'cart': cart, 'form': form})

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user: Any = request.user
        cart = Cart(request)

        if len(cart) == 0:
            messages.warning(request, 'Ваша корзина пуста.')
            return redirect('products:product_list')

        form = OrderCreateForm(request.POST)
        if form.is_valid():
            # Формируем снимок данных доставки
            full_shipping_info = (
                f"{form.cleaned_data['full_name']}, "
                f"Тел: {form.cleaned_data['phone']}\n"
                f"{form.cleaned_data['shipping_address']}"
            )
            serializer_payload = {
                'shipping_address': full_shipping_info,
                'payment_method': form.cleaned_data.get('payment_method', Order.PaymentMethod.CARD),
            }

            # Передаем выполнение в сериализатор (бизнес-слой)
            serializer = OrderCreateSerializer(
                data=serializer_payload,
                context={'request': request},
            )
            if serializer.is_valid():
                order = serializer.save()
                messages.success(request, f'Заказ №{order.id} успешно оформлен!')
                return redirect('orders:order_success', order_id=order.id)

            # Если на складе произошли изменения во время оформления
            for field_errors in serializer.errors.values():
                for err in field_errors:
                    messages.error(request, str(err))
            return redirect('orders:cart_detail')

        return render(request, 'checkout.html', {'cart': cart, 'form': form})


class OrderSuccessView(LoginRequiredMixin, View):
    """Страница подтверждения заказа, доступная только его владельцу."""

    def get(self, request: HttpRequest, order_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        user: Any = request.user
        order = get_object_or_404(Order, id=order_id, user=user)
        return render(request, 'order_success.html', {'order': order})