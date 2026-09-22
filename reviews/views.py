"""
Контроллеры обработки и публикации отзывов покупателей через веб-интерфейс.

Реализует требования раздела 3.2 ТЗ.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from rest_framework.exceptions import PermissionDenied, ValidationError

from products.models import Product

from .serializers import ReviewSerializer


@login_required
@require_POST
def add_review(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Обработчик формы добавления отзыва на товар.

    Вся валидация (проверка покупки, уникальность отзыва, лимиты рейтинга)
    делегирована в ReviewSerializer для соблюдения принципа DRY.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)

    # Передаем данные POST и контекст в ReviewSerializer
    serializer = ReviewSerializer(
        data=request.POST,
        context={'request': request, 'product': product},
    )

    try:
        if serializer.is_valid():
            serializer.save()
            messages.success(request, 'Спасибо! Ваш отзыв успешно опубликован.')
        else:
            # Извлекаем ошибки валидации полей (например, rating)
            for err_list in serializer.errors.values():
                for err in err_list:
                    messages.error(request, str(err))
    except PermissionDenied as e:
        # Ошибка отсутствия факта покупки товара (раздел 3.2 ТЗ)
        messages.error(request, str(e.detail))
    except ValidationError as e:
        # Ошибка повторного отзыва (UniqueConstraint)
        messages.warning(request, str(e.detail[0] if isinstance(e.detail, list) else e.detail))

    return redirect(product.get_absolute_url())
