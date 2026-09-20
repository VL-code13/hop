"""
Контроллеры обработки и публикации отзывов покупателей.

Реализует требования раздела 3.2 ТЗ:
- Отзыв можно оставить только после покупки и оплаты товара.
- Один пользователь = один отзыв на товар (ограничение UniqueConstraint).
- Рейтинг — целое число от 1 до 5 (валидация в модели).
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from orders.models import Order
from products.models import Product

from .forms import ReviewForm
from .models import Review


@login_required  # Только авторизованный пользователь может оставить отзыв
@require_POST  # Разрешаем только POST — отзыв создаётся, но не читается этим эндпоинтом
def add_review(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Добавляет отзыв на товар через веб-форму.

    Бизнес-правила (раздел 3.2 ТЗ):
    1. Пользователь должен быть авторизован (@login_required).
    2. Пользователь должен купить товар — заказ со статусом PAID или DELIVERED.
    3. Один отзыв на товар от одного пользователя (UniqueConstraint в модели).

    @login_required гарантирует, что request.user — авторизованный пользователь,
    а не AnonymousUser. Аннотация `user: Any` сужает тип для mypy без рантайм-проверок:
    mypy перестаёт ругаться на доступ к .profile, передачу в фильтры и т.д.
    """
    # Сужаем тип: декоратор @login_required уже отсёк AnonymousUser в рантайме.
    # Any убирает ошибки mypy без накладных расходов на isinstance-проверку.
    user: Any = request.user

    # Находим товар или возвращаем 404. is_active=True скрывает удалённые товары.
    product = get_object_or_404(Product, id=product_id, is_active=True)

    # --- Проверка 1: факт покупки ---
    # Ищем заказ текущего пользователя, в котором есть данный товар,
    # и статус заказа — PAID (оплачен) или DELIVERED (доставлен).
    # Заказы в статусе PENDING (корзина/ожидание оплаты) не дают права на отзыв.
    has_purchased: bool = Order.objects.filter(
        user=user,
        items__product=product,  # JOIN через OrderItem
        status__in=[Order.Status.PAID, Order.Status.DELIVERED],
    ).exists()

    if not has_purchased:
        # Покупки нет — показываем ошибку и возвращаем на страницу товара.
        messages.error(
            request,
            'Оставить отзыв можно только на товар, который вы уже приобрели и оплатили.',
        )
        return redirect(product.get_absolute_url())

    # --- Проверка 2: повторный отзыв ---
    # UniqueConstraint в модели Review не даёт создать второй отзыв на уровне БД,
    # но мы проверяем здесь, чтобы вернуть понятное сообщение, а не 500-ю ошибку.
    if Review.objects.filter(product=product, user=user).exists():
        messages.warning(request, 'Вы уже оставляли отзыв на данный товар.')
        return redirect(product.get_absolute_url())

    # --- Сохранение отзыва ---
    # ReviewForm валидирует рейтинг (1–5) и текст комментария.
    form = ReviewForm(request.POST)
    if form.is_valid():
        # commit=False — создаём объект Review в памяти, но не пишем в БД.
        # Нужно, чтобы проставить product и user до сохранения.
        review = form.save(commit=False)
        review.product = product
        review.user = user
        review.save()
        messages.success(request, 'Спасибо! Ваш отзыв успешно опубликован.')
    else:
        # Форма невалидна — рейтинг вне диапазона или пустой комментарий.
        messages.error(request, 'Пожалуйста, проверьте правильность заполнения формы.')

    # Возвращаем на страницу товара — там отображается список отзывов.
    return redirect(product.get_absolute_url())
