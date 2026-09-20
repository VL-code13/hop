"""
Контроллеры оплаты заказов.

Реализует требования раздела 3.4 ТЗ («Оформление заказа: эмуляция оплаты»).
Контроллеры являются «тонкими» и делегируют проверки в PaymentService.
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import View

from .services import (
    InvalidOrderStateError,
    OrderAlreadyPaidError,
    PaymentService,
)


class ProcessPaymentView(LoginRequiredMixin, View):
    """
    Тонкий контроллер эмуляции оплаты заказа.
    Отвечает только за валидацию сессии, вызов сервиса и HTTP-редиректы.
    """

    def post(self, request: HttpRequest, order_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        """Принимает запрос на оплату и передает управление в PaymentService."""
        try:
            # Валидация и получение заказа перенесены в сервис
            order = PaymentService.get_payable_order(order_id=order_id, user=request.user)
        except ObjectDoesNotExist:
            messages.error(request, 'Заказ не найден.')
            return redirect('users:account')
        except OrderAlreadyPaidError as e:
            messages.info(request, str(e))
            return redirect('users:account')
        except InvalidOrderStateError as e:
            messages.error(request, str(e))
            return redirect('users:account')

        # Получаем метод оплаты из POST-формы
        payment_method = request.POST.get('payment_method', 'card')

        # Проводим транзакцию через сервисный слой
        PaymentService.process_payment(
            order=order,
            payment_method=payment_method,
            simulate_success=True,
        )

        messages.success(
            request,
            f'Заказ #{order.id} успешно оплачен! Теперь вы можете оставить отзыв на приобретенные товары.',
        )
        return redirect('orders:order_success', order_id=order.id)
