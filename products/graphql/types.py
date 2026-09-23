"""GraphQL-типы для каталога продуктов и аналитики.

ProductType и CategoryType — минимальные представления, которых достаточно
для аналитических запросов. Полноценный каталог клиент получает через REST
(`/api/products/`), а в GraphQL мы отдаём только то, что нужно для дашборда.
"""

from decimal import Decimal

import strawberry
import strawberry_django
from strawberry.scalars import Decimal as DecimalScalar

from products.models import Category, Product


@strawberry_django.type(Category)
class CategoryType:
    """Категория товаров (минимальная карточка)."""

    id: strawberry.ID
    name: strawberry.auto
    slug: strawberry.auto


@strawberry_django.type(Product)
class ProductType:
    """Товар в каталоге (минимальная карточка для аналитики)."""

    id: strawberry.ID
    name: strawberry.auto
    slug: strawberry.auto
    price: DecimalScalar
    stock: strawberry.auto
    is_active: strawberry.auto
    category: CategoryType


@strawberry.type
class PopularProduct:
    """Строка в рейтинге популярных товаров.

    Не связана с моделью Product напрямую — это результат агрегации
    (GROUP BY product_id + SUM(quantity)). Product здесь — обычное поле,
    которое заполняется вручную в резолвере.
    """

    product: ProductType
    units_sold: int
    revenue: DecimalScalar


@strawberry.type
class StockStatus:
    """Состояние складского остатка конкретного товара.

    Используется и для low_stock, и для out_of_stock — поля одинаковые,
    отличается только логика отбора.
    """

    product: ProductType
    stock: int
    threshold: int
    deficit: int  # сколько единиц не хватает до порога (0 для out_of_stock — товара просто нет)