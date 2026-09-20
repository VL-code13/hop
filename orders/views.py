"""
Контроллеры корзины и оформления заказов.

Реализует требования разделов 3.3 (корзина) и 3.4 (оформление заказа) ТЗ:
- Корзина хранится в сессии (неавторизованный пользователь может собирать).
- Заказ оформляется только авторизованным пользователем (LoginRequiredMixin).
- При оформлении проверяются остатки на складе и списываются.
- Все операции по созданию заказа — в одной DB-транзакции (transaction.atomic).
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

from .cart import Cart  # Класс-обёртка над сессионной корзиной
from .forms import OrderCreateForm
from .models import Order, OrderItem


class CartDetailView(View):
    """
    Отображение содержимого корзины.

    Доступно без авторизации — корзина хранится в сессии.
    Просто рендерит шаблон cart_detail.html, передавая объект Cart.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Cart(request) читает корзину из session или создаёт пустую.
        cart = Cart(request)
        return render(request, 'cart_detail.html', {'cart': cart})


class CartAddView(View):
    """
    Добавление товара в сессионную корзину.

    Принимает product_id из URL и quantity из POST-данных.
    Проверяет остаток на складе перед добавлением.
    """

    def post(self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)

        # Находим активный товар или возвращаем 404.
        product = get_object_or_404(Product, id=product_id, is_active=True)

        # Если товар закончился — не даём добавить, показываем предупреждение.
        if product.stock <= 0:
            messages.warning(request, f'Товар «{product.name}» временно отсутствует на складе.')
            return redirect('orders:cart_detail')

        # Парсим количество из POST. По умолчанию 1.
        # try/except защищает от некорректного ввода (буквы, пустая строка).
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            quantity = 1

        # Cart.add() сам проверит, что quantity не превышает stock.
        cart.add(product=product, quantity=quantity)
        messages.success(request, f'Товар «{product.name}» добавлен в корзину.')
        return redirect('orders:cart_detail')


class CartUpdateView(View):
    """
    Обновление количества единиц товара в корзине.

    В отличие от CartAddView, здесь override_quantity=True —
    точное количество перезаписывается, а не прибавляется.
    """

    def post(self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id, is_active=True)

        try:
            quantity = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            messages.error(request, 'Некорректное количество.')
            return redirect('orders:cart_detail')

        # override_quantity=True — заменяем, а не прибавляем.
        # Cart.add() ограничит quantity остатком на складе (product.stock).
        cart.add(product=product, quantity=quantity, override_quantity=True)
        return redirect('orders:cart_detail')


class CartRemoveView(View):
    """Удаление позиции из корзины (не зависит от остатков на складе)."""

    def post(self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        cart = Cart(request)
        product = get_object_or_404(Product, id=product_id)
        cart.remove(product)
        messages.info(request, f'Товар «{product.name}» удален из корзины.')
        return redirect('orders:cart_detail')


class OrderCreateView(LoginRequiredMixin, View):
    """
    Создание заказа на основе сессионной корзины.

    LoginRequiredMixin: только авторизованный пользователь может оформить заказ.
    Неавторизованного перенаправляет на страницу входа (login_url).

    Аннотация `user: Any` сужает тип request.user для mypy:
    LoginRequiredMixin уже отсёк AnonymousUser в рантайме,
    Any убирает ошибки mypy без накладных расходов на isinstance.
    """

    # Куда перенаправлять неавторизованного пользователя.
    login_url = reverse_lazy('users:login')

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Отображение страницы оформления заказа (checkout).

        Предзаполняет форму данными из профиля пользователя (если есть):
        ФИО, телефон, адрес доставки — чтобы не вводить вручную.
        """
        user: Any = request.user

        cart = Cart(request)
        if len(cart) == 0:
            # Пустая корзина — нечего оформлять, отправляем в каталог.
            messages.warning(request, 'Ваша корзина пуста.')
            return redirect('products:product_list')

        # Предзаполнение формы из профиля пользователя.
        # get_full_name() возвращает "Имя Фамилия" или пустую строку.
        # Если пусто — берём username как запасной вариант.
        initial_data: dict[str, Any] = {
            'full_name': user.get_full_name() or user.username,
        }
        # hasattr защищает от случая, когда профиль ещё не создан
        # (например, сигнал не отработал или пользователь создан через shell).
        if hasattr(user, 'profile'):
            initial_data['phone'] = user.profile.phone or ''
            initial_data['shipping_address'] = user.profile.default_shipping_address or ''

        form = OrderCreateForm(initial=initial_data)
        return render(request, 'checkout.html', {'cart': cart, 'form': form})

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Обработка отправленной формы оформления заказа.

        Валидирует форму, проверяет остатки на складе, создаёт заказ
        и позиции заказа в одной транзакции, списывает остатки.
        """
        user: Any = request.user

        cart = Cart(request)
        if len(cart) == 0:
            messages.warning(request, 'Ваша корзина пуста.')
            return redirect('products:product_list')

        form = OrderCreateForm(request.POST)
        if form.is_valid():
            # Собираем данные доставки из формы в одну строку.
            full_name = form.cleaned_data['full_name']
            phone = form.cleaned_data['phone']
            address = form.cleaned_data['shipping_address']
            full_shipping_info = f'{full_name}, Тел: {phone}\n{address}'
            payment_method = form.cleaned_data.get('payment_method', Order.PaymentMethod.CASH)

            # --- Проверка остатков ДО транзакции ---
            # Делаем это вне transaction.atomic(), чтобы не откатывать
            # транзакцию, если остатки изменились пока пользователь заполнял форму.
            for item in cart:
                product = item['product']
                if product.stock < item['quantity']:
                    messages.error(
                        request,
                        f'Товар «{product.name}» осталось {product.stock} шт. '
                        f'У вас в корзине {item["quantity"]} шт. Уменьшите количество.',
                    )
                    return redirect('orders:cart_detail')

            # --- Создание заказа в одной транзакции ---
            # transaction.atomic() гарантирует: если что-то упадёт на любом шаге,
            # все изменения (заказ, позиции, списание остатков) откатятся.
            with transaction.atomic():
                # Создаём заголовок заказа со статусом PENDING (ожидает оплаты).
                order = Order.objects.create(
                    user=user,
                    shipping_address=full_shipping_info,
                    total_price=Decimal(str(cart.get_total_price())),
                    status=Order.Status.PENDING,
                    payment_method=payment_method,
                )

                # Создаём позиции заказа и списываем остатки со склада.
                for item in cart:
                    product = item['product']
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        price=item['price'],
                        quantity=item['quantity'],
                    )
                    # Уменьшаем остаток на складе на количество в заказе.
                    # update_fields=['stock'] — сохраняем только это поле,
                    # чтобы не перезаписать другие изменения (если есть).
                    product.stock -= item['quantity']
                    product.save(update_fields=['stock'])

            # Очищаем корзину после успешного оформления.
            cart.clear()
            messages.success(request, f'Заказ №{order.id} успешно оформлен!')
            return redirect('orders:order_success', order_id=order.id)

        # Форма невалидна — возвращаем на страницу оформления с ошибками.
        return render(request, 'checkout.html', {'cart': cart, 'form': form})


class OrderSuccessView(LoginRequiredMixin, View):
    """
    Страница подтверждения успешно созданного заказа.

    Показывает номер и детали заказа. Доступна только владельцу заказа
    (get_object_or_404 с фильтром user=request.user — чужой заказ даёт 404).
    """

    def get(self, request: HttpRequest, order_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        user: Any = request.user
        # Фильтр user=user гарантирует, что пользователь видит только свои заказы.
        order = get_object_or_404(Order, id=order_id, user=user)
        return render(request, 'order_success.html', {'order': order})
