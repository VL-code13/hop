"""Маршруты веб-интерфейса каталога товаров."""

from django.urls import path
from . import views

app_name: str = 'products'

urlpatterns = [
    path('', views.ProductListView.as_view(), name='list'),
    path('category/<slug:category_slug>/', views.ProductListView.as_view(), name='list_by_category'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='detail'),
]
