"""
Контроллеры аутентификации, регистрации и управления личным кабинетом (/account/).
Реализует требования разделов 2 («session auth») и 3.5 («Личный кабинет») ТЗ.
"""

from typing import Any
from django.contrib import messages
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from orders.models import Order
from .forms import (
    ProfileUpdateForm,
    StyledPasswordChangeForm,
    UserLoginForm,
    UserRegistrationForm,
    UserUpdateForm,
)


class UserRegisterView(CreateView):
    """
    Регистрация нового покупателя на базе CBV (раздел 3.5 ТЗ).
    После создания производит авто-вход (session auth) и перенаправляет в каталог / (раздел 3.1 ТЗ).
    """

    form_class = UserRegistrationForm
    template_name = 'register.html'
    success_url = reverse_lazy('products:list')

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Редирект авторизованного пользователя в /account/ (раздел 3.5 ТЗ)."""
        if request.user.is_authenticated:
            return redirect('users:account')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: UserRegistrationForm) -> HttpResponse:
        """Сохраняет аккаунт, логинит в сессию и выводит flash-сообщение (раздел 3.3 и 3.5 ТЗ)."""
        user = form.save()
        auth_login(self.request, user, backend='users.backends.EmailOrUsernameModelBackend')
        messages.success(self.request, 'Добро пожаловать в Hop & Barley!')
        return redirect(self.success_url)


class CustomLoginView(LoginView):
    """
    Вход покупателя на базе session-based auth (раздел 2 и 3.5 ТЗ).
    Использует адаптированный шаблон login.html.
    """

    authentication_form = UserLoginForm
    template_name = 'login.html'
    redirect_authenticated_user = True

    def form_valid(self, form: UserLoginForm) -> HttpResponse:
        """Flash-сообщение об успешной авторизации."""
        messages.success(self.request, 'Вы успешно вошли в личный кабинет.')
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    """
    Безопасный выход из системы методом POST (раздел 3.5 ТЗ: «вход/выход»).
    Перенаправляет на витрину / (раздел 3.1 ТЗ).
    """

    next_page = reverse_lazy('products:list')

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Информационное сообщение о выходе из сессии."""
        if request.user.is_authenticated:
            messages.info(self.request, 'Вы вышли из учетной записи.')
        return super().dispatch(request, *args, **kwargs)


@login_required
def account_view(request: HttpRequest) -> HttpResponse:
    """
    Личный кабинет покупателя (/account/ по разделу 3.5 ТЗ).

    Включает:
    1. Редактирование профиля и адреса доставки (раздел 3.5 ТЗ);
    2. Смену пароля без сброса авторизации (update_session_auth_hash);
    3. Историю заказов с оптимизацией prefetch_related (раздел 3.5 и 6.1 ТЗ).
    """
    if not hasattr(request.user, 'profile'):
        from .models import Profile
        Profile.objects.create(user=request.user)

    if request.method == 'POST':
        action: str = request.POST.get('action', '')

        # Сценарий А: Редактирование личных данных и адреса (раздел 3.5 ТЗ)
        if action == 'update_profile':
            user_form = UserUpdateForm(request.POST, instance=request.user)
            profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
            password_form = StyledPasswordChangeForm(user=request.user)

            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, 'Данные профиля успешно обновлены.')
                return redirect('users:account')
            else:
                messages.error(request, 'Пожалуйста, проверьте корректность заполнения профиля.')

        # Сценарий Б: Смена пароля (раздел 3.5 ТЗ)
        elif action == 'change_password':
            user_form = UserUpdateForm(instance=request.user)
            profile_form = ProfileUpdateForm(instance=request.user.profile)
            password_form = StyledPasswordChangeForm(user=request.user, data=request.POST)

            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Пароль успешно изменен.')
                return redirect('users:account')
            else:
                messages.error(request, 'Ошибка при смене пароля. Проверьте введенные данные.')
        else:
            user_form = UserUpdateForm(instance=request.user)
            profile_form = ProfileUpdateForm(instance=request.user.profile)
            password_form = StyledPasswordChangeForm(user=request.user)
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)
        password_form = StyledPasswordChangeForm(user=request.user)

    # Оптимизация запросов через prefetch_related во избежание N+1 (раздел 3.1 и 6.1 ТЗ)
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related('items__product')
        .order_by('-created_at')
    )

    context: dict[str, Any] = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'orders': orders,
    }
    return render(request, 'account.html', context)


@login_required
@require_POST
def delete_account_view(request: HttpRequest) -> HttpResponse:
    """
    Мягкое удаление профиля (Soft Delete).

    Вместо физического удаления выставляет is_active = False.
    Это предотвращает каскадное удаление данных Order и OrderItem (раздел 4 ТЗ),
    сохраняя финансовую историю заказов для админки и аналитики (раздел 3.6 ТЗ).
    """
    user = request.user
    user.is_active = False
    user.save(update_fields=['is_active'])

    auth_logout(request)
    messages.info(
        request,
        'Ваш аккаунт деактивирован. Финансовая история заказов сохранена в архиве.',
    )
    return redirect('products:list')