"""Корневая GraphQL-схема проекта Hop & Barley.

Собирает Query-классы из всех доменных приложений в единый граф.
Каждое приложение само описывает свои аналитические резолверы в
graphql/analytics.py и (при необходимости) свои типы в graphql/types.py.

Здесь только агрегация — никакой бизнес-логики.
"""

import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension

# ─── Аналитические запросы по доменам ───
from orders.graphql.analytics import OrderAnalyticsQuery
from products.graphql.analytics import ProductAnalyticsQuery
from users.graphql.analytics import UserAnalyticsQuery

# ─── Пользовательские запросы (публичные) ───
from users.graphql.queries import UserQuery


@strawberry.type
class Query(
    # Публичные запросы, доступные без авторизации.
    UserQuery,
    # Аналитика — каждый резолвер защищён @staff_only.
    OrderAnalyticsQuery,
    ProductAnalyticsQuery,
    UserAnalyticsQuery,
):
    """Корневой тип Query.

    Все поля собираются по MRO: сначала UserQuery, затем аналитика.
    Если в разных классах окажутся поля с одинаковыми именами — Strawberry
    поднимет ошибку при сборке схемы. Это хорошо: конфликты обнаруживаются
    сразу, а не в рантайме.
    """

    @strawberry.field
    def health(self) -> str:
        """Проверка живости эндпоинта.

        Удобно для мониторинга: `curl -X POST /graphql/ -d '{"query":"{health}"}'`.

        Returns:
            Строка 'ok'.
        """
        return 'ok'


#: Итоговая схема, которую обслуживает /graphql/.
#: DjangoOptimizerExtension автоматически добавляет select_related и
#: prefetch_related там, где резолверы читают связанные поля модели.
#: Это спасает от N+1 без ручной оптимизации QuerySet'ов.
schema = strawberry.Schema(
    query=Query,
    extensions=[DjangoOptimizerExtension],
)