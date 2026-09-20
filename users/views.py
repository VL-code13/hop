"""
Контроллеры аутентификации, регистрации и личного кабинета пользователя.

Реализует требования разделов 3.5 (личный кабинет, soft delete)
и 3.7 (управление профилем, смена пароля) ТЗ.
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
    """
    Контроллер входа в систему по имени пользователя или Email.

    Использует кастомную форму UserLoginForm, которая принимает
    и username, и email (бэкенд EmailOrUsernameModelBackend).
    redirect_authenticated_user=True — если пользователь уже вошёл,
    он не увидит форму входа, а будет перенаправлен дальше.
    """

    form_class = UserLoginForm
    template_name = 'login.html'
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        """
        Определяет URL для редиректа после успешного входа.

        Приоритет: GET-параметр next (get_redirect_url), иначе — каталог товаров.
        """
        return self.get_redirect_url() or str(reverse_lazy('products:product_list'))

    def form_invalid(self, form: Any) -> HttpResponse:
        """
        Добавляет сообщение об ошибке, если логин/пароль неверны.

        Stock LoginView не показывает messages — мы добавляем для UX.
        """
        messages.error(self.request, 'Неверный email/логин или пароль. Пожалуйста, проверьте введённые данные.')
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    """
    Контроллер завершения сеанса пользователя.

    LogoutView по умолчанию принимает только POST (защита от CSRF).
    next_page — куда перенаправить после выхода (каталог товаров).
    """

    next_page = reverse_lazy('products:product_list')  # type: ignore[assignment]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Добавляет прощальное сообщение перед стандартным выходом."""
        messages.info(request, 'Вы успешно вышли из системы.')
        return super().post(request, *args, **kwargs)


class RegisterView(FormView):
    """
    Регистрация нового пользователя с автоматическим входом.

    После успешной регистрации пользователь сразу авторизуется
    (login с указанием бэкенда) и попадает в личный кабинет.
    Профиль создаётся автоматически через сигнал (users/signals.py).
    """

    template_name = 'register.html'
    form_class = UserRegisterForm
    success_url = reverse_lazy('users:account')

    def form_valid(self, form: Any) -> HttpResponse:
        """
        Сохраняет пользователя (form.save), авторизует его и перенаправляет.

        backend= указан явно, т.к. у нас кастомный бэкенд,
        принимающий и email, и username.
        """
        user = form.save()
        # login() пишет ID пользователя в сессию.
        # backend — строка пути к классу бэкенда аутентификации.
        login(self.request, user, backend='users.backends.EmailOrUsernameModelBackend')
        messages.success(self.request, 'Регистрация прошла успешно! Добро пожаловать в клуб.')
        # redirect вместо self.success_url — чтобы сработал редирект,
        # а не просто отрисовалась страница по URL.
        return redirect(self.success_url)


class ReactivatePasswordResetConfirmView(PasswordResetConfirmView):
    """
    Подтверждение сброса пароля с автоматической реактивацией пользователя.

    Если пользователь ранее деактивировал аккаунт (is_active=False),
    то при сбросе пароля мы снова активируем его — это позволяет
    «восстановить» аккаунт без обращения в поддержку.
    """

    template_name = 'password_reset_confirm.html'
    success_url = reverse_lazy('users:password_reset_complete')

    def form_valid(self, form: Any) -> HttpResponse:
        """
        Если аккаунт неактивен — активируем его перед сменой пароля.

        form.user — объект пользователя, для которого сбрасывается пароль.
        update_fields=['is_active'] — сохраняем только это поле,
        чтобы не затереть пароль, который Django сменит в super().form_valid().
        """
        user = form.user
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
            messages.success(
                self.request, 'Ваш аккаунт был успешно реактивирован! Все оформленные ранее заказы сохранены.'
            )
        return super().form_valid(form)


class AccountView(LoginRequiredMixin, View):
    """
    Личный кабинет покупателя.

    Объединяет три функции на одной странице:
    1. История заказов (Order.objects.filter(user=user)).
    2. Редактирование профиля (ProfileUpdateForm).
    3. Смена пароля (PasswordChangeCustomForm).

    Обрабатывает GET (отображение) и POST (обновление профиля или смена пароля).
    Действие определяется скрытым полем 'action' в форме.

    LoginRequiredMixin гарантирует, что request.user — авторизованный пользователь.
    Аннотация `user: Any` сужает тип для mypy без рантайм-проверок.
    """

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Отображение личного кабинета: заказы, форма профиля, форма пароля.

        prefetch_related('items__product') — подгружает позиции и товары
        двухуровневым JOIN, чтобы избежать N+1 при отрисовке истории заказов.
        """
        user: Any = request.user

        # История заказов — только свои, новые сверху.
        orders = Order.objects.filter(user=user).prefetch_related('items__product').order_by('-created_at')

        # Форма редактирования профиля.
        # instance=user — форма привязана к текущему пользователю.
        # initial — предзаполнение полей phone и address из профиля.
        profile_form = ProfileUpdateForm(
            instance=user,
            initial={
                'phone': user.profile.phone,
                'default_shipping_address': user.profile.default_shipping_address,
            },
        )

        # Форма смены пароля (Django PasswordChangeForm).
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
        """
        Обработка отправки формы профиля или смены пароля.

        Поле 'action' из POST определяет, какая форма отправлена:
        - 'update_profile' — сохранение изменений профиля.
        - 'change_password' — смена пароля.

        Если форма невалидна — перерисовываем страницу с ошибками
        (через self.get в конце метода).
        """
        user: Any = request.user
        action = request.POST.get('action')

        if action == 'update_profile':
            # Привязываем POST-данные к существующему пользователю.
            profile_form = ProfileUpdateForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Профиль успешно обновлен.')
                return redirect('users:account')
            messages.error(request, 'Пожалуйста, исправьте ошибки в данных профиля.')

        elif action == 'change_password':
            # data=request.POST — валидация старого и нового паролей.
            password_form = PasswordChangeCustomForm(user=user, data=request.POST)
            if password_form.is_valid():
                # save() меняет пароль пользователя в БД.
                password_form.save()
                # update_session_auth_hash — обновляет хеш сессии,
                # чтобы пользователь не разлогинился после смены пароля.
                # Без этого Django выкинет на страницу входа.
                update_session_auth_hash(request, user)
                messages.success(request, 'Пароль успешно изменен.')
                return redirect('users:account')
            messages.error(request, 'Ошибка при смене пароля. Проверьте правильность введенных данных.')

        # Если действие не распознано или форма невалидна —
        # перерисовываем страницу (self.get вернёт context с формами).
        return self.get(request, *args, **kwargs)


class DeleteAccountView(LoginRequiredMixin, View):
    """
    Мягкое удаление профиля (Soft Delete) по разделу 3.5 ТЗ.

    Не удаляем пользователя из БД (чтобы сохранить историю заказов),
    а помечаем его is_active=False. Пользователь не сможет войти,
    но его заказы и отзывы остаются в системе.

    ReactivatePasswordResetConfirmView позволяет восстановить аккаунт
    через сброс пароля.
    """

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Деактивирует пользователя и разлогинивает его."""
        user: Any = request.user
        user.is_active = False
        # Сохраняем только поле is_active, не трогая остальные.
        user.save(update_fields=['is_active'])
        logout(request)
        messages.info(request, 'Ваш аккаунт был успешно деактивирован.')
        return redirect('products:product_list')


# as_view() превращает класс в вызываемую функцию для urls.py.
delete_account_view = DeleteAccountView.as_view()
