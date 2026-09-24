"""Аналитические резолверы по товарам.

Требование ТЗ 3.9: «Продукты: популярные, остатки».

Все запросы возвращают небольшие агрегаты — никаких N+1, никаких
переборов в Python. Всё считает БД.
"""

from decimal import Decimal
from typing import Final

import strawberry
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from strawberry.types import Info

from config.graphql.cache import cache_metric
from config.graphql.permissions import staff_only
from orders.models import Order, OrderItem
from products.graphql.types import PopularProduct, StockStatus
from products.models import Product

#: Статусы заказа, при которых выручка считается «заработанной».
#: ВАЖНО: значения должны совпадать с Order.Status в вашей модели.
#: Если у вас они капсом (PAID, SHIPPED, DELIVERED) — поправьте здесь.
REVENUE_STATUSES: Final[list[str]] = [
    Order.Status.PAID,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
]
#: Порог, ниже которого товар попадает в «мало на складе».
DEFAULT_LOW_STOCK_THRESHOLD: Final[int] = 5


@strawberry.type
class ProductAnalyticsQuery:
    """Аналитические запросы по товарам (только для staff)."""

    @strawberry.field
    @staff_only
    @cache_metric(ttl=600, prefix='products')  # популярные меняются редко — 10 минут
    def popular_products(
        self,
        info: Info,
        limit: int = 10,
        min_units_sold: int = 1,
    ) -> list[PopularProduct]:
        """Топ продаваемых товаров за всё время.

        Популярность измеряется в единицах проданного товара (SUM(quantity)),
        а не в количестве заказов — иначе один крупный опт исказил бы рейтинг.

        Args:
            info: GraphQL-контекст (используется декоратором staff_only).
            limit: Сколько позиций вернуть в топе. Защита от чрезмерных запросов.
            min_units_sold: Минимальное количество проданных единиц,
                чтобы попасть в топ. Отсеивает случайные единичные продажи.

        Returns:
            Список PopularProduct, отсортированный по убыванию units_sold.
            Пустой список, если продаж нет.
        """
        # Агрегируем на стороне БД: один SQL-запрос с GROUP BY.
        # Аннотируем суммой quantity и выручкой (quantity * unit_price).
        rows = (
            OrderItem.objects.filter(order__status__in=REVENUE_STATUSES)
            .values('product_id')
            .annotate(
                units_sold=Sum('quantity'),
                # DecimalField нужен, чтобы Coalesce вернул Decimal, а не int
                # при пустом результате. Value('0.00') — значение по умолчанию.
                revenue=Coalesce(
                    Sum(F('quantity') * F('price'), output_field=DecimalField(max_digits=14, decimal_places=2)),
                    Value(Decimal('0.00'), output_field=DecimalField(max_digits=14, decimal_places=2)),
                ),
            )
            .filter(units_sold__gte=min_units_sold)
            .order_by('-units_sold')[:limit]
        )

        # Забираем связанные продукты одним запросом, чтобы не было N+1.
        product_ids = [row['product_id'] for row in rows]
        products_by_id = Product.objects.filter(id__in=product_ids).in_bulk()

        # Собираем итоговые объекты. Пропускаем строки, у которых продукт
        # удалён (in_bulk может не вернуть его) — на всякий случай.
        result: list[PopularProduct] = []
        for row in rows:
            product = products_by_id.get(row['product_id'])
            if product is None:
                continue
            result.append(
                PopularProduct(
                    product=product,  # type: ignore[arg-type]
                    units_sold=row['units_sold'],
                    revenue=row['revenue'].quantize(Decimal('0.01')),
                )
            )
        return result

    @strawberry.field
    @staff_only
    @cache_metric(ttl=120, prefix='products')  # низкие остатки — 2 минуты
    def low_stock_products(
        self,
        info: Info,
        threshold: int = DEFAULT_LOW_STOCK_THRESHOLD,
        limit: int = 50,
    ) -> list[StockStatus]:
        """Товары с остатком ниже порога (но не нулевым).

        Нужны менеджеру для закупок: «осталось 2 штуки, пора заказывать».
        Нулевой остаток — отдельный резолвер out_of_stock_products.

        Args:
            info: GraphQL-контекст.
            threshold: Порог, ниже которого товар считается «на исходе».
            limit: Максимум позиций в ответе.

        Returns:
            Список StockStatus, отсортированный по возрастанию остатка
            (самые «горящие» — первыми).
        """
        # stock > 0 — исключаем нулевой остаток (он в out_of_stock).
        # stock < threshold — оставляем только тех, кого надо докупить.
        queryset = (
            Product.objects.filter(is_active=True, stock__gt=0, stock__lt=threshold)
            .select_related('category')
            .order_by('stock')[:limit]
        )

        return [
            StockStatus(
                product=product,  # type: ignore[arg-type] # ← передаём модель, Strawberry конвертирует сам
                stock=product.stock,
                threshold=threshold,
                deficit=threshold - product.stock,
            )
            for product in queryset
        ]

    @strawberry.field
    @staff_only
    @cache_metric(ttl=60, prefix='products')  # out-of-stock критичен — 1 минута
    def out_of_stock_products(self, info: Info, limit: int = 100) -> list[StockStatus]:
        """Активные товары с нулевым остатком.

        Самый критичный отчёт: товар ещё продаётся, но купить нельзя —
        прямая потеря выручки.

        Args:
            info: GraphQL-контекст.
            limit: Максимум позиций в ответе.

        Returns:
            Список StockStatus с stock=0.
        """
        queryset = Product.objects.filter(is_active=True, stock=0).select_related('category').order_by('name')[:limit]

        return [
            StockStatus(
                product=product,  # type: ignore[arg-type]
                stock=0,
                threshold=DEFAULT_LOW_STOCK_THRESHOLD,
                # Для нулевого остатка deficit = сам порог, ведь дефицит
                # считается до «здорового» уровня, а не до нуля.
                deficit=DEFAULT_LOW_STOCK_THRESHOLD,
            )
            for product in queryset
        ]
