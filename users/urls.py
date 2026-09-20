"""Маршруты аутентификации, регистрации и профиля пользователей."""

from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import CustomPasswordResetForm

app_name = 'users'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('account/', views.AccountView.as_view(), name='account'),
    path('account/delete/', views.DeleteAccountView.as_view(), name='delete_account'),

    # Восстановление пароля и реактивация профиля
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='password_reset_form.html',
            email_template_name='password_reset_email.html',
            form_class=CustomPasswordResetForm,
            success_url=reverse_lazy('users:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password-reset-confirm/<uidb64>/<token>/',
        views.ReactivatePasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
]
