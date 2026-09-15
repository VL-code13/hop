"""Контроллеры оплаты заказа."""

from typing import Any
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import View
from orders.models import Order
from .services import PaymentService


class ProcessPaymentView(LoginRequiredMixin, View):
    """Обработчик совершения мок-платежа."""

    def post(self, request: HttpRequest, order_id: int, *args: Any, **kwargs: Any) -> HttpResponse:
        """Выполняет эмуляцию оплаты заказа."""
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status == Order.Status.PAID:
            messages.info(request, f'Заказ #{order.id} уже оплачен.')
            return redirect('users:account')

        payment_method = request.POST.get('payment_method', 'card')

        PaymentService.process_payment(
            order=order,
            payment_method=payment_method,
            simulate_success=True,
        )

        messages.success(request, f'Заказ #{order.id} успешно оплачен! Теперь вы можете оставить отзыв на купленные товары.')
        return redirect('orders:order_success', order_id=order.id)