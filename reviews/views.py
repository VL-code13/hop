"""Контроллеры обработки и публикации отзывов покупателей через веб-интерфейс.

Реализует требования раздела 3.2 ТЗ.

Вся валидация (проверка покупки, уникальность отзыва, лимиты рейтинга)
делегирована в ``ReviewSerializer``. DRF-исключения конвертируются в
``django.contrib.messages`` — web-интерфейс работает через редиректы,
а не через HTTP-ошибки JSON, в отличие от REST API.
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from rest_framework.exceptions import PermissionDenied, ValidationError

from products.models import Product

from .serializers import ReviewSerializer


def _extract_error_messages(detail: Any) -> list[str]:
    """Нормализует ``err.detail`` из DRF в плоский список строк.

    DRF может вернуть ``dict`` (ошибки полей), ``list`` (non_field) или
    скаляр (редкий случай). Все три варианта превращаются в список строк,
    который удобно итерировать в цикле ``messages.error``.

    Args:
        detail: ``err.detail`` из DRF ``ValidationError``.

    Returns:
        list[str]: Плоский список читаемых сообщений об ошибках.
    """
    if isinstance(detail, dict):
        messages_list: list[str] = []
        for field_errors in detail.values():
            if isinstance(field_errors, list):
                messages_list.extend(str(e) for e in field_errors)
            else:
                messages_list.append(str(field_errors))
        return messages_list
    if isinstance(detail, list):
        return [str(e) for e in detail]
    return [str(detail)]


@login_required
@require_POST
def add_review(request: HttpRequest, product_id: int) -> HttpResponse:
    """Обработчик формы добавления отзыва на товар.

    Поток:

    1. Проверяет, что товар активен.
    2. Прогоняет POST через ``ReviewSerializer`` с ``raise_exception=True``,
       чтобы получить явные исключения вместо ``serializer.errors``.
    3. Конвертирует DRF-исключения в ``messages``:

       - ``PermissionDenied`` (нет покупки) → ``messages.error``;
       - ``ValidationError`` (дубль, плохой рейтинг) → ``messages.warning``.

    4. При успехе сохраняет отзыв и показывает ``messages.success``.

    Args:
        request: HTTP-запрос (метод POST, авторизованный пользователь).
        product_id: ID товара из URL.

    Returns:
        HttpResponse: Редирект на страницу товара в любом случае.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)

    serializer = ReviewSerializer(
        data=request.POST,
        context={'request': request, 'product': product},
    )

    try:
        serializer.is_valid(raise_exception=True)
    except PermissionDenied as err:
        # Нет факта покупки — 403 в API, красное сообщение в web.
        messages.error(request, str(err.detail))
        return redirect(product.get_absolute_url())
    except ValidationError as err:
        # Дубль отзыва, невалидный рейтинг, пустой комментарий и т.п.
        for msg in _extract_error_messages(err.detail):
            messages.warning(request, msg)
        return redirect(product.get_absolute_url())

    serializer.save()
    messages.success(request, 'Спасибо! Ваш отзыв успешно опубликован.')
    return redirect(product.get_absolute_url())
