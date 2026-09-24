"""
Маршрутизация веб-интерфейса каталога товаров.

Реализует требования разделов 3.1 и 3.2 ТЗ.
"""

from django.urls import path

from . import views

app_name: str = 'products'

urlpatterns = [
    # Главная витрина каталога
    path('', views.ProductListView.as_view(), name='product_list'),
    # Фильтрация по категории через URL-слаг
    path('category/<slug:category_slug>/', views.ProductListView.as_view(), name='list_by_category'),
    # Детальная страница карточки товара (имя product_detail для совпадения с get_absolute_url)
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    # Страница рецептов и гидов для домашних пивоваров
    path('guides-recipes/', views.GuidesRecipesView.as_view(), name='guides_recipes'),
]
