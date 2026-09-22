"""
Настройки отображения пользователей и профилей в административной панели Django.

Реализует требования раздела 3.6 ТЗ («Управление пользователями»).
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    """Инлайн-блок профиля покупателя внутри карточки пользователя Django."""

    model = Profile
    can_delete = False
    verbose_name_plural = 'Данные профиля и доставки'
    fields = ('phone', 'default_shipping_address', 'avatar')


# Перерегистрация UserAdmin для показа профиля в карточке пользователя
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Расширенная админка пользователя со связкой профиля доставки."""

    inlines = [ProfileInline]
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Отдельный список профилей в админке для быстрого поиска по контактам."""

    list_display = ('id', 'user', 'phone', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone', 'default_shipping_address')
    readonly_fields = ('created_at', 'updated_at')
