"""Главная конфигурация маршрутов URL проекта Hop & Barley."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # 1. Панель администратора Django (раздел 3.6 ТЗ)
    path('admin/', admin.site.urls),

    # 2. Каталог товаров и витрина (раздел 3.1 и 3.2 ТЗ)
    # Корневой маршрут ('') ведет на products.urls
    path('', include('products.urls', namespace='products')),

    # 3. Корзина и оформление заказов (раздел 3.3 и 3.4 ТЗ)
    path('orders/', include('orders.urls', namespace='orders')),

    # 4. Пользовательские отзывы (раздел 3.2 ТЗ)
    path('reviews/', include('reviews.urls', namespace='reviews')),
]

# Раздача загруженных изображений (MEDIA_ROOT) в режиме отладки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
