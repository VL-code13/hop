"""Контроллеры оплаты заказов.

Реализует требования раздела 3.4 ТЗ («Оформление заказа: эмуляция оплаты»).
Контроллеры «тонкие»: проверки и бизнес-логика делегированы в PaymentService.
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import View

from .services import (
    InvalidOrderStateError,
    OrderAlreadyPaidError,
    OrderNotFoundError,
    PaymentError,
    PaymentService,
)


class ProcessPaymentView(LoginRequiredMixin, View):
    """Тонкий контроллер эмуляции оплаты заказа.

    Обрабатывает POST, вызывает сервис, показывает сообщение и делает редирект.
    Все исключения ``PaymentError`` (и подклассы) обрабатываются здесь:
    сбой платёжного шлюза не должен приводить к 500-й.
    """

    def post(self, request: HttpRequest, order_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        """Принимает запрос на оплату и передаёт управление в PaymentService."""
        try:
            order = PaymentService.get_payable_order(
                order_id=order_id,
                user=request.user,
            )
            payment_method = request.POST.get('payment_method', 'card')

            # process_payment тоже в try — race между двумя вызовами
            # может привести к OrderAlreadyPaidError прямо здесь.
            PaymentService.process_payment(
                order=order,
                user=request.user,
                payment_method=payment_method,
                simulate_success=True,
            )
        except OrderNotFoundError:
            messages.error(request, 'Заказ не найден.')
            return redirect('users:account')
        except OrderAlreadyPaidError as err:
            messages.info(request, str(err))
            return redirect('users:account')
        except InvalidOrderStateError as err:
            messages.error(request, str(err))
            return redirect('users:account')
        except PaymentError as err:
            # Catch-all на случай новых подклассов PaymentError в будущем.
            messages.error(request, str(err))
            return redirect('users:account')

        messages.success(
            request,
            f'Заказ #{order.id} успешно оплачен! Теперь вы можете оставить отзыв на приобретенные товары.',
        )
        return redirect('orders:order_success', order_id=order.id)
