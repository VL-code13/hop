"""
Контроллеры аутентификации, регистрации и личного кабинета пользователя.

Реализует требования разделов 3.5 и 3.7 ТЗ.
"""

from typing import Any
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
)
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, View

from orders.models import Order
from .forms import (
    PasswordChangeCustomForm,
    ProfileUpdateForm,
    UserLoginForm,
    UserRegisterForm,
)


class CustomLoginView(LoginView):
    """Контроллер входа в систему по имени пользователя или Email."""

    form_class = UserLoginForm
    template_name = 'login.html'
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        return self.get_redirect_url() or str(reverse_lazy('products:product_list'))

    def form_invalid(self, form: Any) -> HttpResponse:
        messages.error(
            self.request,
            'Неверный email/логин или пароль. Пожалуйста, проверьте введённые данные.'
        )
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """Контроллер завершения сеанса пользователя."""

    next_page = reverse_lazy('products:product_list')

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        messages.info(request, 'Вы успешно вышли из системы.')
        return super().post(request, *args, **kwargs)


class RegisterView(FormView):
    """Регистрация нового пользователя с автоматическим входом."""

    template_name = 'register.html'
    form_class = UserRegisterForm
    success_url = reverse_lazy('users:account')

    def form_valid(self, form: Any) -> HttpResponse:
        user = form.save()
        login(self.request, user, backend='users.backends.EmailOrUsernameModelBackend')
        messages.success(self.request, 'Регистрация прошла успешно! Добро пожаловать в клуб.')
        return redirect(self.success_url)


class ReactivatePasswordResetConfirmView(PasswordResetConfirmView):
    """Подтверждение сброса пароля с автоматической реактивацией пользователя."""

    template_name = 'password_reset_confirm.html'
    success_url = reverse_lazy('users:password_reset_complete')

    def form_valid(self, form: Any) -> HttpResponse:
        user = form.user
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
            messages.success(
                self.request,
                'Ваш аккаунт был успешно реактивирован! Все оформленные ранее заказы сохранены.'
            )
        return super().form_valid(form)


class AccountView(LoginRequiredMixin, View):
    """Личный кабинет покупателя: история заказов, редактирование профиля и смена пароля."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        orders = Order.objects.filter(user=user).prefetch_related('items__product').order_by('-created_at')
        profile_form = ProfileUpdateForm(instance=user, initial={
            'phone': user.profile.phone,
            'default_shipping_address': user.profile.default_shipping_address,
        })
        password_form = PasswordChangeCustomForm(user=user)

        context = {
            'user': user,
            'profile': user.profile,
            'orders': orders,
            'profile_form': profile_form,
            'password_form': password_form,
        }
        return render(request, 'account.html', context)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Профиль успешно обновлен.')
                return redirect('users:account')
            messages.error(request, 'Пожалуйста, исправьте ошибки в данных профиля.')

        elif action == 'change_password':
            password_form = PasswordChangeCustomForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Пароль успешно изменен.')
                return redirect('users:account')
            messages.error(request, 'Ошибка при смене пароля. Проверьте правильность введенных данных.')

        return self.get(request, *args, **kwargs)


class DeleteAccountView(LoginRequiredMixin, View):
    """Мягкое удаление профиля (Soft Delete) по разделу 3.5 ТЗ."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        user.is_active = False
        user.save(update_fields=['is_active'])
        logout(request)
        messages.info(request, 'Ваш аккаунт был успешно деактивирован.')
        return redirect('products:product_list')


delete_account_view = DeleteAccountView.as_view()