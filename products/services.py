"""Сервисный слой каталога товаров.

Выносит из представлений логику фильтрации, поиска и сортировки,
чтобы views оставались «тонкими» и отвечали только за HTTP.

Реализует требования раздела 3.1 ТЗ («Каталог и поиск»):
- фильтрация по категории;
- фильтрация по диапазону цен;
- полнотекстовый поиск по названию и описанию;
- сортировка по новизне, цене, популярности.
"""

from decimal import Decimal, InvalidOperation
from typing import Final

from django.db.models import Avg, Q, QuerySet

from products.models import Product

# Белый список сортировок (защита от SQL-инъекций через ?sort=).
# Публичный (не _) — используется в тестах и может пригодиться в API.
SORT_MAPPING: Final[dict[str, str]] = {
    'price_asc': 'price',
    'price_desc': '-price',
    'popular': '-avg_rating',
    'newest': '-created_at',
    'name': 'name',
}

# Сортировка по умолчанию, если параметр отсутствует или неизвестен.
DEFAULT_ORDER: Final[str] = '-created_at'


def get_catalog_queryset(
    *,
    category_slug: str | None = None,
    search_query: str | None = None,
    min_price: str | None = None,
    max_price: str | None = None,
    sort: str | None = None,
) -> QuerySet[Product]:
    """Возвращает QuerySet активных товаров с применёнными фильтрами.

    Функция объединяет все операции чтения витрины в одном месте:
    фильтрацию по категории, поиск, диапазон цен и сортировку.
    Используется как веб-представлением (`ProductListView`), так и
    потенциальными другими потребителями (management-команды, экспорт).

    Все параметры keyword-only и опциональны. Некорректные значения цен
    молча игнорируются (пользователь не должен видеть 500-ю из-за опечатки
    в query-параметре). Неизвестный `sort` откатывается к `DEFAULT_ORDER`.

    Запрос оптимизирован:
    - `select_related('category')` — JOIN категории за один запрос;
    - `annotate(avg_rating=...)` — средний рейтинг товара на уровне SQL.

    Args:
        category_slug: Slug категории для фильтрации (`category__slug`).
            Если None — фильтр не применяется.
        search_query: Подстрока для поиска в названии и описании
            (регистронезависимо, `icontains`). Если None или пустая
            строка — поиск не применяется.
        min_price: Минимальная цена в виде строки (для корректного
            парсинга `Decimal`). Нечисловое значение игнорируется.
        max_price: Максимальная цена, аналогично `min_price`.
        sort: Ключ сортировки из `SORT_MAPPING`. Неизвестное значение
            откатывается к `DEFAULT_ORDER`.

    Returns:
        QuerySet[Product]: Активные товары, отфильтрованные и
        отсортированные согласно переданным параметрам.

    Examples:
        >>> get_catalog_queryset(category_slug='hops', sort='price_asc')
        >>> get_catalog_queryset(search_query='citra', min_price='500')
    """
    queryset: QuerySet[Product] = (
        Product.objects.filter(is_active=True).select_related('category').annotate(avg_rating=Avg('reviews__rating'))
    )

    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)

    if search_query:
        queryset = queryset.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

    queryset = _apply_price_range(queryset, min_price, max_price)

    order_field: str = SORT_MAPPING.get(sort or DEFAULT_ORDER, DEFAULT_ORDER)
    return queryset.order_by(order_field)


def _apply_price_range(
    queryset: QuerySet[Product],
    min_price: str | None,
    max_price: str | None,
) -> QuerySet[Product]:
    """Применяет фильтр по диапазону цен, игнорируя нечисловой ввод.

    Вспомогательная функция для `get_catalog_queryset`. Вынесена отдельно,
    чтобы изолировать `try/except` от основной логики.

    Args:
        queryset: Исходный QuerySet товаров.
        min_price: Минимальная цена (строка) или None.
        max_price: Максимальная цена (строка) или None.

    Returns:
        QuerySet[Product]: Тот же QuerySet с добавленными
        `price__gte` / `price__lte` фильтрами (или без них, если
        значения отсутствуют или невалидны).
    """
    try:
        if min_price:
            queryset = queryset.filter(price__gte=Decimal(min_price))
        if max_price:
            queryset = queryset.filter(price__lte=Decimal(max_price))
    except (InvalidOperation, ValueError):
        # Некорректный ввод (не число) — молча пропускаем фильтр.
        # Это осознанный компромисс: UI не должен падать из-за опечатки
        # в URL. В логах это можно отследить по access-логам nginx.
        pass
    return queryset
