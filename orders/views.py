"""Контроллеры управления содержимым корзины и жизненным циклом заказов."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import mail_admins, send_mail
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Product
from .cart import Cart
from .forms import OrderCreateForm
from .models import Order, OrderItem


def cart_detail(request: HttpRequest) -> HttpResponse:
    """Отображает страницу содержимого корзины покупателя."""
    return render(request, 'orders/cart_detail.html', {'cart': Cart(request)})


@require_POST
def cart_add(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Добавляет товар в корзину с валидацией остатка на складе.

    Складывает уже имеющееся количество товара с новым запрошенным.
    """
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)

    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity <= 0:
            messages.error(request, 'Количество должно быть больше нуля.')
            return redirect('orders:cart_detail')
    except (ValueError, TypeError):
        messages.error(request, 'Указано некорректное числовое значение.')
        return redirect('orders:cart_detail')

    already_in_cart = cart.cart.get(str(product_id), {}).get('quantity', 0)

    if already_in_cart + quantity > product.stock:
        messages.error(
            request,
            f'Невозможно добавить {quantity} шт. На складе всего {product.stock} шт., '
            f'из них в корзине уже {already_in_cart} шт.'
        )
        return redirect('orders:cart_detail')

    cart.add(product=product, quantity=quantity, override_quantity=False)
    messages.success(request, f'Товар «{product.name}» добавлен в корзину.')
    return redirect('orders:cart_detail')


@require_POST
def cart_update(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Перезаписывает точное количество единиц товара в корзине.
    """
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        messages.error(request, 'Указано некорректное значение количества.')
        return redirect('orders:cart_detail')

    if quantity < 1:
        cart.remove(product)
        messages.info(request, f'Товар «{product.name}» удален из корзины.')
    elif quantity > product.stock:
        messages.error(
            request,
            f'На складе доступно только {product.stock} шт. товара «{product.name}».'
        )
    else:
        cart.add(product=product, quantity=quantity, override_quantity=True)
        messages.success(request, f'Количество для «{product.name}» обновлено.')

    return redirect('orders:cart_detail')


@require_POST
def cart_remove(request: HttpRequest, product_id: int) -> HttpResponse:
    """Удаляет указанную позицию из сессионной корзины."""
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    messages.info(request, f'Товар «{product.name}» удален из корзины.')
    return redirect('orders:cart_detail')


@login_required
def order_create(request: HttpRequest) -> HttpResponse:
    """
    Создает заказ, списывает остатки и отправляет уведомления по email.

    Использует атомарную транзакцию для исключения race conditions.
    """
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, "Ваша корзина пуста.")
        return redirect('products:list')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        city = request.POST.get('city', '').strip()
        address_raw = request.POST.get('shipping_address', '').strip()
        payment_method = request.POST.get('payment_method', Order.PaymentMethod.CARD)

        # Сборка полного адреса с контактами
        combined_address = (
            f"Получатель: {full_name}\n"
            f"Тел: {phone}\n"
            f"Город: {city}\n"
            f"Адрес: {address_raw}"
        )

        with transaction.atomic():
            # Проверка наличия достаточного количества товаров на складе
            for item in cart:
                prod: Product = item['product']
                if prod.stock < item['quantity']:
                    messages.error(
                        request,
                        f"Недостаточно остатка для '{prod.name}' (в наличии: {prod.stock})."
                    )
                    return redirect('orders:cart_detail')

            order = Order.objects.create(
                user=request.user,
                payment_method=payment_method,
                shipping_address=combined_address,
                total_price=cart.get_total_price(),
                status=Order.Status.PENDING,
            )

            for item in cart:
                prod = item['product']
                OrderItem.objects.create(
                    order=order,
                    product=prod,
                    price=item['price'],
                    quantity=item['quantity'],
                )
                # Списание складского остатка
                prod.stock -= item['quantity']
                prod.save(update_fields=['stock'])

        cart.clear()

        # Email-уведомления (раздел 3.4 ТЗ)
        if request.user.email:
            send_mail(
                subject=f"Заказ #{order.id} оформлен",
                message=f"Здравствуйте, {request.user.username}! Ваш заказ на сумму {order.total_price} ₽ принят.",
                from_email=None,
                recipient_list=[request.user.email],
                fail_silently=True,
            )
        mail_admins(
            subject=f"Новый заказ #{order.id}",
            message=f"Пользователь {request.user.username} оформил заказ #{order.id} на сумму {order.total_price} ₽.",
            fail_silently=True,
        )

        return render(request, 'orders/order_success.html', {'order': order})

    return render(request, 'orders/checkout.html', {'cart': cart})


@login_required
def order_history(request: HttpRequest) -> HttpResponse:
    """История заказов текущего пользователя (раздел 3.5 ТЗ)."""
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related('items__product')
        .order_by('-created_at')
    )
    return render(request, 'orders/order_history.html', {'orders': orders})