"""
Настройки отображения моделей каталога в административной панели Django.

Реализует требования раздела 3.6 ТЗ («Админ-панель: управление товарами,
категориями, аннотации, фильтры, кастомные actions»).
"""

from django.contrib import admin, messages
from django.db.models import Count, QuerySet, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from orders.models import OrderItem

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Конфигурация админ-зоны для товарных категорий (раздел 3.6 ТЗ)."""

    list_display = (
        'name',
        'slug',
        'parent',
        'products_count',
        'created_at',
    )
    list_filter = ('parent',)
    search_fields = ('name', 'slug')
    # Автоматическое заполнение слага из названия при вводе в админке
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Category]:
        """
        Аннотация количества привязанных товаров для аналитики (раздел 3.6 ТЗ).
        Исключает N+1 запросов при отображении списка категорий.
        """
        queryset = super().get_queryset(request)
        return queryset.annotate(total_products=Count('products'))

    @admin.display(description='Кол-во товаров', ordering='total_products')
    def products_count(self, obj: Category) -> int:
        """Отображает вычисленное количество товаров в категории."""
        return getattr(obj, 'total_products', 0)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Конфигурация админ-зоны для управления товарами (раздел 3.6 ТЗ)."""

    list_display = (
        'name',
        'category',
        'price',
        'stock',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'category', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    # Быстрое редактирование остатка, цены и активности прямо в таблице списка
    list_editable = ('stock', 'price', 'is_active')
    # Добавлены оба временных поля в readonly
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    actions = ['make_active', 'make_inactive']

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        """Оптимизация запроса: подгрузка категории через JOIN (select_related)."""
        queryset = super().get_queryset(request)
        return queryset.select_related('category')

    # ─────────────────────── Кастомная страница удаления ───────────────────────

    def delete_view(
        self,
        request: HttpRequest,
        object_id: str,
        extra_context: dict | None = None,
    ) -> HttpResponse:
        """Перехватывает удаление товара.

        Стандартная страница удаления с PROTECT-ошибкой выглядит как
        «невозможно удалить» — плохой UX. Вместо этого показываем
        кастомную страницу с объяснением и двумя действиями:

        - **Деактивировать товар** — снимает флаг ``is_active``,
          товар пропадает с витрины, но остаётся в истории заказов.
        - **Вернуться назад** — отмена, редирект на referer.

        Если товар **не** встречается ни в одном заказе, делегируем
        стандартному ``super().delete_view`` — обычное удаление.
        """
        product = self.get_object(request, object_id)
        if product is None:
            return super().delete_view(request, object_id, extra_context)

        order_items = OrderItem.objects.filter(product=product)
        if not order_items.exists():
            # Товар нигде не заказан — разрешаем стандартное удаление.
            return super().delete_view(request, object_id, extra_context)

        # Товар есть в заказах — показываем кастомную страницу.
        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'deactivate':
                product.is_active = False
                product.save(update_fields=['is_active'])
                messages.success(
                    request,
                    f'Товар «{product.name}» деактивирован и убран с витрины. '
                    f'История заказов сохранена.',
                )
                return self._return_to_referer(request)

            if action == 'cancel':
                return self._return_to_referer(request)

        context = {
            **self.admin_site.each_context(request),
            'product': product,
            'order_items': order_items.select_related(
                'order', 'order__user'
            ).order_by('-order__created_at')[:10],
            'order_items_count': order_items.count(),
            'orders_count': order_items.values('order').distinct().count(),
            'total_quantity': order_items.aggregate(
                total=Sum('quantity')
            )['total'] or 0,
            'opts': self.model._meta,
            'title': f'Удаление товара «{product.name}»',
            'is_popup': request.GET.get('_popup') == '1',
        }
        return render(
            request,
            'admin/products/product_delete_blocked.html',
            context,
        )

    def _return_to_referer(self, request: HttpRequest) -> HttpResponse:
        """Возвращает пользователя на страницу, откуда он пришёл.

        Обычно это карточка заказа (``/admin/orders/order/<id>/change/``)
        или список товаров. Fallback — список товаров.
        """
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect(reverse('admin:products_product_changelist'))

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Product | None = None,
    ) -> bool:
        """Скрывает иконку «Удалить» в popup-режиме inline-формы заказа.

        Когда админ добавляет позицию в заказ через autocomplete, Django
        может показать ссылку на удаление товара. Удалять товар оттуда
        нельзя — для удаления позиции нужен чекбокс в самой строке inline.
        """
        if request.GET.get('_popup') == '1':
            return False
        return super().has_delete_permission(request, obj)

    # ─────────────────────────── Actions ───────────────────────────

    @admin.action(description='Сделать выбранные товары активными')
    def make_active(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовый action для перевода товаров в статус активных на витрине."""
        updated_count = queryset.update(is_active=True)
        self.message_user(request, f'Активировано товаров: {updated_count}.')

    @admin.action(description='Снять выбранные товары с витрины')
    def make_inactive(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовый action для деактивации товаров (снятия с продажи)."""
        updated_count = queryset.update(is_active=False)
        self.message_user(request, f'Снято с витрины товаров: {updated_count}.')
