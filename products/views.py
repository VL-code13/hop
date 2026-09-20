"""Классы представлений (CBV) для витрины каталога и страниц товаров.
Реализует требования разделов 3.1 («Каталог и поиск») и 3.2 («Страница товара») ТЗ."""
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Avg, Q, QuerySet
from django.views.generic import DetailView, ListView, TemplateView

from products.forms import AddToCartProductForm
from products.models import Category, Product


class ProductListView(ListView):
    """
    Представление каталога товаров.

    Обеспечивает:
    - Пагинацию по 9 товаров на страницу;
    - Полнотекстовый поиск по вхождению в название и описание;
    - Фильтрацию по категории и диапазону цен (min_price, max_price);
    - Сортировку по новинкам, цене и популярности (рейтингу).
    """
    model = Product
    template_name: str = 'product_list.html'
    context_object_name: str = 'products'
    paginate_by = 9

    def get_queryset(self) -> QuerySet[Product]:
        """
        Формирует оптимизированный набор данных товаров с учетом всех GET-фильтров.

        Использует select_related для категории во избежание проблем с N+1 запросами
        и annotate для расчета среднего рейтинга на базе отзывов.
        """
        queryset: QuerySet[Product] = (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .annotate(avg_rating=Avg('reviews__rating'))
        )

        category_slug: str | None = self.kwargs.get('category_slug') or self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        search_query: str = self.request.GET.get('q', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            )

        min_price: str | None = self.request.GET.get('min_price')
        max_price: str | None = self.request.GET.get('max_price')
        try:
            if min_price:
                queryset = queryset.filter(price__gte=Decimal(min_price))
            if max_price:
                queryset = queryset.filter(price__lte=Decimal(max_price))
        except (InvalidOperation, ValueError):
            pass

        sort_parameter: str = self.request.GET.get('sort', 'newest')
        sort_mapping: dict[str, str] = {
            'price_asc': 'price',
            'price_desc': '-price',
            'popular': '-avg_rating',
            'newest': '-created_at',
            'name': 'name',
        }
        order_field: str = sort_mapping.get(sort_parameter, '-created_at')
        return queryset.order_by(order_field)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        context['categories'] = (
            Category.objects.filter(parent__isnull=True)
            .prefetch_related('children')
        )
        context['current_category'] = (
                self.kwargs.get('category_slug') or self.request.GET.get('category', '')
        )
        context['current_sort'] = self.request.GET.get('sort', 'newest')
        context['search_query'] = self.request.GET.get('q', '')
        context['min_price'] = self.request.GET.get('min_price', '')
        context['max_price'] = self.request.GET.get('max_price', '')
        return context


class ProductDetailView(DetailView):
    """
    Представление детальной страницы отдельного товара. (раздел 3.2 ТЗ)

    Отображает исчерпывающую информацию о товаре, форму добавления в корзину
    и список пользовательских отзывов с рейтингами.
    """

    model = Product
    template_name: str = 'product_detail.html'
    context_object_name: str = 'product'
    slug_url_kwarg: str = 'slug'
    slug_field = 'slug'

    def get_queryset(self) -> QuerySet[Product]:
        return (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .prefetch_related('reviews__user')
            .annotate(avg_rating=Avg('reviews__rating'))
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        Передает в шаблон форму выбора количества, список отзывов
        и флаги can_review / has_existing_review.

        can_review: пользователь купил товар (PAID/DELIVERED) и ещё не оставил отзыв.
        has_existing_review: пользователь уже оставил отзыв на этот товар.
        """
        context: dict[str, Any] = super().get_context_data(**kwargs)
        product: Product = self.object  # type: ignore[assignment]
        context['cart_form'] = AddToCartProductForm(max_stock=product.stock)
        context['reviews'] = product.reviews.all().order_by('-created_at')

        from reviews.forms import ReviewForm
        context['review_form'] = ReviewForm()

        can_review = False
        has_existing_review = False
        if self.request.user.is_authenticated:
            from orders.models import Order
            from reviews.models import Review

            has_existing_review = Review.objects.filter(
                product=product, user=self.request.user,
            ).exists()
            if not has_existing_review:
                can_review = Order.objects.filter(
                    user=self.request.user,
                    items__product=product,
                    status__in=[Order.Status.PAID, Order.Status.DELIVERED],
                ).exists()

        context['can_review'] = can_review
        context['has_existing_review'] = has_existing_review
        return context


class GuidesRecipesView(TemplateView):
    """Статическая страница руководств и рецептов для пивоваров."""

    template_name: str = 'guides-recipes.html'
