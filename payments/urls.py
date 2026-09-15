"""Маршруты приложения оплаты."""

from django.urls import path
from .views import ProcessPaymentView

app_name = 'payments'

urlpatterns = [
    path('process/<int:order_id>/', ProcessPaymentView.as_view(), name='process'),
]