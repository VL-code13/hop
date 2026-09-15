"""Главная конфигурация маршрутов URL проекта Hop & Barley."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from orders.api_views import CartAPIView, OrderViewSet
from products.api_views import ProductViewSet
from reviews.api_views import ProductReviewsAPIView
from config.admin import HopBarleyAdminSite

# Заменяем стандартный admin.site на наш расширенный
custom_admin_site = HopBarleyAdminSite(name='custom_admin')

# Переносим зарегистрированные модели в новый сайт
custom_admin_site._registry = admin.site._registry

# Регистрация эндпоинтов REST API каталога и заказов (раздел 3.7 ТЗ)
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='api-products')
router.register(r'orders', OrderViewSet, basename='api-orders')

urlpatterns = [
    # 1. Панель администратора (раздел 3.6 ТЗ)
    path('admin/', custom_admin_site.urls),

    # 2. Пользователи и личный кабинет (раздел 3.5 ТЗ)
    path('users/', include('users.urls', namespace='users')),

    # 3. Корзина и чекаут (разделы 3.3 и 3.4 ТЗ)
    path('', include('orders.urls', namespace='orders')),

    # 4. Отзывы покупателей (раздел 3.2 ТЗ)
    path('reviews/', include('reviews.urls', namespace='reviews')),

    # 5. Веб-интерфейс каталога (разделы 3.1 и 3.2 ТЗ)
    path('', include('products.urls', namespace='products')),

    # 6. REST API эндпоинты (раздел 3.7 ТЗ)
    path('api/', include(router.urls)),
    path('api/cart/', CartAPIView.as_view(), name='api-cart'),
    path('api/products/<int:product_id>/reviews/', ProductReviewsAPIView.as_view(), name='api-product-reviews'),

    # JWT Авторизация в API
    path('api/users/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 7. Документация OpenAPI / Swagger (раздел 3.8 ТЗ)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Эмуляция платежей
    path('payments/', include('payments.urls', namespace='payments')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
