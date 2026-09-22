"""Классы представлений (CBV) для витрины каталога и страниц товаров.

Реализует требования разделов 3.1 («Каталог и поиск») и 3.2 («Страница
товара») ТЗ. Представления «тонкие»: HTTP-специфика — во view, а
фильтрация и бизнес-правила — в сервисном слое
(`products.services`, `reviews.services`).
"""

from typing import Any

from django.db.models import Avg, QuerySet
from django.views.generic import DetailView, ListView, TemplateView

from products.forms import AddToCartProductForm
from products.models import Category, Product
from products.services import get_catalog_queryset


class ProductListView(ListView):
    """Витрина каталога с фильтрами, поиском и сортировкой (раздел 3.1 ТЗ).

    Реализует:
    - пагинацию по 9 товаров на страницу;
    - поиск по вхождению подстроки в название и описание;
    - фильтрацию по категории (path-параметр или GET `?category=`);
    - фильтрацию по диапазону цен (`?min_price=` / `?max_price=`);
    - сортировку по новизне, цене, популярности.

    Вся логика фильтрации делегирована в `get_catalog_queryset`.
    """

    model: type[Product] = Product
    template_name: str = 'product_list.html'
    context_object_name: str = 'products'
    paginate_by: int = 9

    def get_queryset(self) -> QuerySet[Product]:
        """Собирает GET-параметры и передаёт их в сервисный слой.

        Returns:
            QuerySet[Product]: Активные товары с фильтрами и сортировкой,
            пагинируемые Django на уровне ListView.
        """
        return get_catalog_queryset(
            category_slug=(self.kwargs.get('category_slug') or self.request.GET.get('category')),
            search_query=self.request.GET.get('q', '').strip() or None,
            min_price=self.request.GET.get('min_price'),
            max_price=self.request.GET.get('max_price'),
            sort=self.request.GET.get('sort'),
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Добавляет в контекст шаблона состояние фильтров и дерево категорий.

        Returns:
            dict[str, Any]: Стандартный контекст ListView плюс ключи
            `categories`, `current_category`, `current_sort`,
            `search_query`, `min_price`, `max_price` для сохранения
            состояния формы фильтрации.
        """
        context: dict[str, Any] = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(parent__isnull=True).prefetch_related('children')
        context['current_category'] = self.kwargs.get('category_slug') or self.request.GET.get('category', '')
        context['current_sort'] = self.request.GET.get('sort', 'newest')
        context['search_query'] = self.request.GET.get('q', '')
        context['min_price'] = self.request.GET.get('min_price', '')
        context['max_price'] = self.request.GET.get('max_price', '')
        return context


class ProductDetailView(DetailView):
    """Детальная страница товара (раздел 3.2 ТЗ).

    Отображает:
    - карточку товара с оптимизированной загрузкой категории и отзывов;
    - форму добавления в корзину с ограничением по остатку;
    - список отзывов с рейтингами;
    - блок для оставления отзыва (только для покупателей).
    """

    model: type[Product] = Product
    template_name: str = 'product_detail.html'
    context_object_name: str = 'product'
    slug_url_kwarg: str = 'slug'
    slug_field: str = 'slug'

    def get_queryset(self) -> QuerySet[Product]:
        """Возвращает активные товары с оптимизацией запросов.

        `select_related('category')` — JOIN категории за один запрос.
        `prefetch_related('reviews__user')` — загрузка авторов отзывов
        отдельным запросом (защита от N+1 при рендере блока отзывов).
        `annotate(avg_rating=...)` — средний рейтинг на уровне SQL.

        Returns:
            QuerySet[Product]: Активные товары, готовые к детальному
            отображению.
        """
        return (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .prefetch_related('reviews__user')
            .annotate(avg_rating=Avg('reviews__rating'))
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Формирует контекст карточки товара.

        Дополнительно передаёт:
        - `cart_form` — форма добавления в корзину с `max_stock`;
        - `reviews` — список отзывов, отсортированных по дате;
        - `review_form` — пустая форма для нового отзыва;
        - `can_review` / `has_existing_review` — флаги бизнес-правила
          «отзыв только после покупки» (раздел 3.2 ТЗ).

        Returns:
            dict[str, Any]: Контекст для `product_detail.html`.
        """
        context: dict[str, Any] = super().get_context_data(**kwargs)
        product: Product = self.object  # type: ignore[assignment]

        # Ленивые импорты — избегаем циклической зависимости
        # products → reviews → orders → products.
        from reviews.forms import ReviewForm
        from reviews.services import get_review_permissions

        can_review, has_existing_review = get_review_permissions(
            self.request.user,
            product,
        )

        context.update(
            {
                'cart_form': AddToCartProductForm(max_stock=product.stock),
                'reviews': product.reviews.all().order_by('-created_at'),
                'review_form': ReviewForm(),
                'can_review': can_review,
                'has_existing_review': has_existing_review,
            }
        )
        return context


class GuidesRecipesView(TemplateView):
    """Статическая страница руководств и рецептов для домашних пивоваров."""

    template_name: str = 'guides-recipes.html'
