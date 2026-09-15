"""Контроллеры обработки и публикации отзывов покупателей.
Реализует требования раздела 3.2 ТЗ («возможность оставить отзыв только после покупки»)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from orders.models import Order
from products.models import Product
from .forms import ReviewForm
from .models import Review


@login_required
@require_POST
def add_review(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Добавляет отзыв на товар.

    Проверяет:
    1. Покупал ли пользователь этот товар (статус заказа PAID или DELIVERED).
    2. Оставлял ли пользователь отзыв на этот товар ранее (UniqueConstraint).
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)

    # Проверка факта покупки по разделу 3.2 ТЗ
    has_purchased: bool = Order.objects.filter(
        user=request.user,
        items__product=product,
        status__in=[Order.Status.PAID, Order.Status.DELIVERED],
    ).exists()

    if not has_purchased:
        messages.error(
            request,
            "Оставить отзыв можно только на товар, который вы уже приобрели и оплатили.",
        )
        return redirect(product.get_absolute_url())

    if Review.objects.filter(product=product, user=request.user).exists():
        messages.warning(request, "Вы уже оставляли отзыв на данный товар.")
        return redirect(product.get_absolute_url())

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.save()
        messages.success(request, "Спасибо! Ваш отзыв успешно опубликован.")
    else:
        messages.error(request, "Пожалуйста, проверьте правильность заполнения формы.")

    return redirect(product.get_absolute_url())
