"""Маршруты URL для корзины и процессов оформления заказов."""

from django.urls import path
from . import views

app_name: str = 'orders'

urlpatterns = [
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('checkout/', views.order_create, name='checkout'),
    path('history/', views.order_history, name='order_history'),
]