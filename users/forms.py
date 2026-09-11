"""
Формы пользовательского интерфейса для личного кабинета и аутентификации.
Реализует требования раздела 3.5 ТЗ («регистрация, вход/выход, редактирование профиля, смена пароля»).
"""

from typing import Any
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)
from .models import Profile

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    """
    Форма самостоятельной регистрации покупателя (раздел 3.5 ТЗ).

    Использует email в качестве основного идентификатора.
    Реализует реактивацию учетной записи при повторной регистрации,
    чтобы сохранить историю заказов без каскадного удаления (раздел 3.5 и 4 ТЗ).
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'Input',
            'placeholder': 'name@domain.com',
            'autocomplete': 'email',
            'id': 'email',
        }),
        label='Электронная почта',
        help_text='На этот адрес приходят подтверждения заказов по разделу 3.4 ТЗ.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email',)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Применяет стили CSS-класса Input ко всем полям формы."""
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'Input'})

    def clean_email(self) -> str:
        """
        Валидация уникальности почты:
        - Если email занят активным аккаунтом -> ошибка валидации.
        - Если аккаунт был деактивирован (is_active=False) -> разрешается реактивация.
        """
        email: str = self.cleaned_data.get('email', '').strip().lower()
        active_user_exists = User.objects.filter(email__iexact=email, is_active=True).exists()

        if active_user_exists:
            raise forms.ValidationError('Пользователь с таким адресом email уже зарегистрирован.')
        return email

    def save(self, commit: bool = True) -> Any:
        """
        Сохранение формы регистрации:
        - Если аккаунт ранее деактивирован через Soft Delete, он восстанавливается,
          сохраняя связь с заказами Order по разделу 3.5 и 4 ТЗ.
        - Иначе создается новый пользователь, где username равен email.
        """
        email: str = self.cleaned_data.get('email', '').strip().lower()
        inactive_user = User.objects.filter(email__iexact=email, is_active=False).first()

        if inactive_user:
            inactive_user.username = email
            inactive_user.set_password(self.cleaned_data['password1'])
            inactive_user.is_active = True
            if commit:
                inactive_user.save()
            return inactive_user

        user = super().save(commit=False)
        user.email = email
        user.username = email
        if commit:
            user.save()
        return user


class UserLoginForm(AuthenticationForm):
    """
    Форма авторизации покупателя (раздел 3.5 ТЗ: «вход (session auth)»).
    Использует email в качестве логина.
    """

    username = forms.CharField(
        widget=forms.EmailInput(attrs={
            'class': 'Input',
            'placeholder': 'name@domain.com',
            'autocomplete': 'email',
            'id': 'email',
        }),
        label='Электронная почта',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'Input',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
            'id': 'password',
        }),
        label='Пароль',
    )


class UserUpdateForm(forms.ModelForm):
    """
    Форма редактирования профиля (раздел 3.5 ТЗ: «редактирование профиля»).
    Изменяет имя, фамилию и контактный email.
    """

    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'Input', 'id': 'acc-full-name'}),
        label='Имя',
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'Input'}),
        label='Фамилия',
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'Input', 'id': 'acc-email'}),
        label='Электронная почта',
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def clean_email(self) -> str:
        """Проверяет уникальность email среди других пользователей."""
        email: str = self.cleaned_data.get('email', '').strip().lower()
        duplicate = (
            User.objects.filter(email__iexact=email, is_active=True)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if duplicate:
            raise forms.ValidationError('Этот адрес электронной почты уже используется другим аккаунтом.')
        return email


class ProfileUpdateForm(forms.ModelForm):
    """
    Форма редактирования адреса доставки и телефона (раздел 3.5 ТЗ).
    Данные сохраняются для повторных заказов в /checkout/ (раздел 3.4 ТЗ).
    """

    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'Input',
            'placeholder': '+7 (999) 000-00-00',
            'id': 'acc-phone',
        }),
        label='Номер телефона',
    )
    default_shipping_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'Textarea',
            'rows': 3,
            'placeholder': 'Укажите город, улицу, дом и квартиру',
            'id': 'acc-address',
        }),
        label='Основной адрес доставки',
    )

    class Meta:
        model = Profile
        fields = ('phone', 'default_shipping_address')


class StyledPasswordChangeForm(PasswordChangeForm):
    """
    Форма смены пароля в личном кабинете (раздел 3.5 ТЗ: «смена пароля»).
    Стилизована под класс Input.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Накладывает стили оформления Input на поля формы смены пароля."""
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'Input'})