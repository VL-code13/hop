"""
Маршруты URL для аутентификации и профиля пользователя.
Регистрирует пространство имен 'users' для роутинга по разделам 3.5 и 5 ТЗ.
"""

from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

app_name: str = 'users'

urlpatterns = [
    # Аутентификация и регистрация (раздел 3.5 ТЗ)
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('register/', views.UserRegisterView.as_view(), name='register'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),

    # Личный кабинет и деактивация (раздел 3.5 ТЗ)
    path('account/', views.account_view, name='account'),
    path('account/delete/', views.delete_account_view, name='delete_account'),

    # Восстановление доступа по шаблону forgot_password.html
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='forgot_password.html',
            success_url='/users/login/',
        ),
        name='password_reset',
    ),
]