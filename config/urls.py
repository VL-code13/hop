"""
Главная конфигурация маршрутов URL проекта Hop & Barley.

Реализует требования разделов:
- 3.1, 3.2 («Веб-каталог и детальная карточка товара»)
- 3.3, 3.4 («Корзина, чекаут и оформление заказа»)
- 3.5 («Аутентификация, профили и регистрация»)
- 3.6 («Административная панель и аналитика»)
- 3.7 («REST API: каталог, заказы, корзина, отзывы, JWT»)
- 3.8 («Документация Swagger/OpenAPI через drf-spectacular»)
"""

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

from config.admin import HopBarleyAdminSite
from orders.api_views_orders import CartAPIView, OrderViewSet
from products.api_views_products import ProductViewSet
from reviews.api_views_reviews import ProductReviewsAPIView
from users.views import RegisterView  # Контроллер регистрации по ТЗ

# Кастомная панель администратора с аналитикой (раздел 3.6 ТЗ)
custom_admin_site = HopBarleyAdminSite(name='custom_admin')
custom_admin_site._registry = admin.site._registry

# Роутер DRF для ресурсов товаров и заказов (раздел 3.7 ТЗ)
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='api-products')
router.register(r'orders', OrderViewSet, basename='api-orders')

urlpatterns = [
    # 1. Панель администратора
    path('admin/', custom_admin_site.urls),
    # 2. Пользователи и аутентификация (веб-интерфейс, раздел 3.5 ТЗ)
    path('users/', include('users.urls', namespace='users')),
    # 3. Корзина и оформление заказа (веб-интерфейс, разделы 3.3 и 3.4 ТЗ)
    path('', include('orders.urls', namespace='orders')),
    # 4. Пользовательские отзывы (веб-интерфейс, раздел 3.2 ТЗ)
    path('reviews/', include('reviews.urls', namespace='reviews')),
    # 5. Каталог товаров и витрина (главная страница, раздел 3.1 ТЗ)
    path('', include('products.urls', namespace='products')),
    # 6. Эмуляция платежей (раздел 3.4 ТЗ)
    path('payments/', include('payments.urls', namespace='payments')),
    # =========================================================================
    # 7. REST API эндпоинты (раздел 3.7 ТЗ)
    # =========================================================================
    path('api/', include(router.urls)),
    path('api/cart/', CartAPIView.as_view(), name='api-cart'),
    path('api/products/<int:product_id>/reviews/', ProductReviewsAPIView.as_view(), name='api-product-reviews'),
    # Регистрация и JWT-авторизация в API (раздел 3.7 ТЗ)
    path('api/users/register/', RegisterView.as_view(), name='api-user-register'),
    path('api/users/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # =========================================================================
    # 8. Документация OpenAPI / Swagger (раздел 3.8 ТЗ)
    # =========================================================================
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Раздача медиафайлов при локальной разработке
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
