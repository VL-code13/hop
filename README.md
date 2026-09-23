# Hop & Barley — интернет-магазин товаров для крафтового пивоварения

Полнофункциональный веб-сервис на Django 6.1 и Django REST Framework для онлайн-продажи сырья, ингредиентов, рецептурных
наборов и оборудования для домашнего пивоварения.

Архитектура построена по принципу разделения ответственности («тонкие контроллеры, толстый слой
сервисов/сериализаторов»). Использует:

- **атомарное списание остатков** через `F()`-выражения и `filter(stock__gte=qty).update(...)` — защита от overselling
  даже там, где `select_for_update()` не работает;
- **гибридную сессионную корзину** — работает для анонимных и авторизованных пользователей;
- **JWT-аутентификацию** через `djangorestframework-simplejwt`;
- **двухуровневую защиту от двойной оплаты** — `select_for_update` + `UniqueConstraint` на БД;
- **нормализацию телефонов** через `users/phone.py` — единый формат `+7XXXXXXXXXX` в БД;
- **DRY бизнес-правило отзывов** — «только после покупки» живёт в `reviews/services.py` и переиспользуется в web и API;
- **кастомную аналитическую панель** с дашбордом, складским контролем и журналом заказов;
- **GraphQL-эндпоинт** `/graphql/` на Strawberry — единая точка для аналитических запросов по заказам, товарам и
  пользователям;
- **кеширование аналитических метрик** через `@cache_metric` — per-resolver TTL, работает на любом Django cache backend;
- **pre-commit hooks** для автоматического `ruff`, `ruff-format`, `mypy` и `pytest` перед коммитом и push;
- **управление зависимостями через Poetry** — lock-файл, разделение main/dev-групп, изоляция окружения.

[![CI](https://github.com/VL-code13/hop/actions/workflows/ci.yml/badge.svg?branch=dev_3st_week)](https://github.com/VL-code13/hop/actions/workflows/ci.yml)

## Содержание

- [Технологический стек](#технологический-стек)
- [Архитектурная структура проекта](#архитектурная-структура-проекта)
- [Быстрый старт](#быстрый-старт)
- [Переменные окружения (.env)](#переменные-окружения-env)
- [Реализованная бизнес-логика](#реализованная-бизнес-логика)
- [Спецификация REST API](#спецификация-rest-api)
- [Примеры запросов с JWT](#примеры-запросов-с-jwt)
- [GraphQL API](#graphql-api)
- [Аутентификация и безопасность](#аутентификация-и-безопасность)
- [OpenAPI и интерактивная документация](#openapi-и-интерактивная-документация)
- [Тестирование и контроль качества](#тестирование-и-контроль-качества)
- [CI/CD](#cicd)
- [Панель администратора и аналитика](#панель-администратора-и-аналитика)
- [Ограничения и известные компромиссы](#ограничения-и-известные-компромиссы)

---

## Технологический стек

| Категория             | Технология / Библиотека                                       | Назначение                                                   |
|-----------------------|---------------------------------------------------------------|--------------------------------------------------------------|
| Язык                  | Python 3.12                                                   | Runtime                                                      |
| Менеджер зависимостей | **Poetry 2.x**                                                | Lockfile, изоляция venv, разделение main/dev                 |
| Бэкенд-платформа      | Django 6.1.1                                                  | Веб-ядро, ORM, маршрутизация, шаблонизатор, сигналы          |
| REST API              | Django REST Framework 3.18                                    | Сериализация, валидация запросов, ViewSets, permissions      |
| **GraphQL**           | **Strawberry GraphQL 0.327 + strawberry-graphql-django 0.89** | **Аналитический эндпоинт `/graphql/`**                       |
| JWT-авторизация       | djangorestframework-simplejwt 5.5.1                           | Выпуск, проверка и ротация Access / Refresh токенов          |
| Схема OpenAPI         | drf-spectacular 0.30.0                                        | Генерация OpenAPI 3.0, интерактивных Swagger UI и ReDoc      |
| Статические файлы     | WhiteNoise 6.12                                               | Раздача сжатой кэшируемой статики с манифестным хешированием |
| СУБД (Production)     | PostgreSQL 16 + psycopg 3.3                                   | Продакшн-база с поддержкой строгой изоляции транзакций       |
| СУБД (Development)    | SQLite                                                        | Встроенная база для ускоренной локальной разработки          |
| Тестирование          | pytest 9.1 + pytest-django + pytest-cov                       | Набор из 67+ тестов с автоматическим замером покрытия        |
| Статический анализ    | Ruff 0.16 + Mypy 1.13 + django-stubs                          | Линтинг по PEP 8 и статическая типизация                     |
| Контроль качества     | pre-commit 4.6.2                                              | Git-хуки для ruff, mypy, pytest                              |
| Контейнеризация       | Docker + Docker Compose                                       | Изоляция сервисов веб-приложения и сервера БД                |

---

## Архитектурная структура проекта

```text
hop-and-barley/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions: ruff, mypy, pytest на PostgreSQL
├── config/                     # Настройки проекта
│   ├── settings/
│   │   ├── base.py             # Базовые параметры, JWT, WhiteNoise, DRF, Strawberry
│   │   ├── development.py      # SQLite, DEBUG=True, локальная разработка
│   │   ├── prod.py             # PostgreSQL, security-настройки, строгий WhiteNoise
│   │   ├── test.py             # SQLite in-memory, MD5-хешер паролей — для pytest
│   │   └── ci.py               # PostgreSQL, locmem email, для CI и pytest
│   ├── graphql/                # GraphQL-ядро (не Django-приложение!)
│   │   ├── cache.py            # @cache_metric — кеширование аналитических резолверов
│   │   ├── context.py          # GraphQLContext + кастомный HopBarleyGraphQLView
│   │   ├── middleware.py       # GraphQLJWTAuthMiddleware — аутентификация по JWT
│   │   ├── permissions.py      # @staff_only — декоратор проверки прав
│   │   └── schema.py           # Корневая схема: агрегация Query-классов доменов
│   ├── admin.py                # HopBarleyAdminSite с аналитическим дашбордом
│   ├── urls.py                 # Центральный диспетчер: UI, REST API, /graphql/
│   ├── wsgi.py
│   └── asgi.py
├── products/                   # Каталог товаров и категорий (раздел 3.1 ТЗ)
│   ├── models.py               # Category, Product (свойство in_stock)
│   ├── services.py             # get_catalog_queryset: фильтры, поиск, сортировка
│   ├── views.py                # ProductListView, ProductDetailView (тонкие CBV)
│   ├── api_views_products.py   # ProductViewSet
│   ├── serializers.py          # ProductList/DetailSerializer, CategorySerializer
│   ├── forms.py                # AddToCartProductForm
│   ├── admin.py                # Администрирование каталога, actions
│   ├── graphql/                # GraphQL-слой приложения
│   │   ├── types.py            # ProductType, CategoryType, PopularProduct, StockStatus
│   │   └── analytics.py        # popularProducts, lowStock, outOfStock
│   ├── tests.py                # Тесты витрины, поиска, фильтров
│   └── tests_services.py       # Тесты сервисного слоя (без HTTP)
├── orders/                     # Корзина и заказы (разделы 3.3, 3.4 ТЗ)
│   ├── models.py               # Order, OrderItem (snapshot цены)
│   ├── cart.py                 # Cart — сессионная корзина
│   ├── views.py                # CBV корзины и чекаута
│   ├── api_views_orders.py     # CartAPIView, OrderViewSet
│   ├── serializers.py          # Атомарный чекаут: F() + select_for_update
│   ├── forms.py                # OrderCreateForm + нормализация телефона
│   ├── context_processors.py   # Инъекция cart в шаблоны
│   ├── admin.py                # Обработка заказов, аналитика, actions
│   ├── graphql/
│   │   ├── types.py            # OrderType, OrderItemType, OrderMetrics, TrendPoint
│   │   └── analytics.py        # orderMetrics, orderTrends
│   └── tests.py                # Тесты корзины и списания остатков
├── reviews/                    # Отзывы покупателей (раздел 3.2 ТЗ)
│   ├── models.py               # Review + UniqueConstraint(product, user)
│   ├── services.py             # get_review_permissions (единое бизнес-правило)
│   ├── views.py                # Web-обработчик с raise_exception=True
│   ├── api_views_reviews.py    # ProductReviewsAPIView
│   ├── serializers.py          # ReviewSerializer (DRY через services)
│   ├── forms.py                # ReviewForm
│   ├── admin.py                # Модерация отзывов
│   ├── tests.py                # Web + API тесты
│   └── tests_services.py       # Тесты бизнес-правила
├── payments/                   # Сервис платежей (раздел 3.4 ТЗ)
│   ├── models.py               # PaymentTransaction (UUID PK, unique SUCCESS)
│   ├── services.py             # PaymentService: атомарные операции
│   ├── views.py                # Тонкий контроллер с обработкой PaymentError
│   ├── admin.py                # Журнал транзакций (read-only)
│   └── tests.py                # Идемпотентность, IDOR, БД-инвариант
├── users/                      # Пользователи и профили (раздел 3.5 ТЗ)
│   ├── models.py               # Profile (1:1 с User)
│   ├── phone.py                # normalize_phone, format_phone, phone_validator
│   ├── backends.py             # EmailOrUsernameModelBackend
│   ├── signals.py              # Автосоздание Profile
│   ├── forms.py                # Формы входа, регистрации, профиля
│   ├── views.py                # ЛК, смена пароля, soft delete, реактивация
│   ├── admin.py                # Инлайн профиля
│   ├── graphql/
│   │   ├── types.py            # UserType, UserActivityMetrics
│   │   ├── queries.py          # me — публичный резолвер текущего пользователя
│   │   └── analytics.py        # userActivity, repeatPurchaseTrend, customerLifetimeValue
│   └── tests.py                # Аутентификация, JWT, soft delete, phone
├── tests/                      # Интеграционные тесты, не привязанные к приложению
│   └── graphql/                # Тесты GraphQL-эндпоинта
│       ├── test_permissions.py       # Аноним / FORBIDDEN / staff / health
│       ├── test_order_analytics.py   # orderMetrics, orderTrends
│       ├── test_product_analitics.py # lowStockProducts, popularProducts
│       ├── test_user_queries.py      # me, аналитика пользователей
│       └── test_cache.py             # кеширование метрик + порядок проверки прав
├── templates/                  # Шаблоны оформления
├── static/                     # CSS, JS, изображения
├── .coveragerc                 # Правила исключений для coverage
├── .dockerignore
├── .env.example
├── docker-compose.yaml
├── Dockerfile
├── pyproject.toml              # Poetry + Ruff + Mypy (единый конфиг)
├── poetry.lock                 # Зафиксированные версии зависимостей
├── pytest.ini                  # Конфигурация pytest
├── conftest.py                 # Глобальные pytest-фикстуры (включая JWT и _clear_cache)
├── manage.py
└── README.md
```

---

## Быстрый старт

### Требования

| Инструмент | Версия            | Установка                                                                            |
|------------|-------------------|--------------------------------------------------------------------------------------|
| Python     | 3.12+             | [python.org](https://www.python.org/downloads/)                                      |
| Poetry     | 2.0+              | `pipx install poetry` или `curl -sSL https://install.python-poetry.org \| python3 -` |
| Docker     | 24+ (опционально) | [docs.docker.com](https://docs.docker.com/get-docker/)                               |

### Вариант A: Локальная разработка (SQLite, без Docker)

**1. Клонируйте репозиторий:**

```bash
git clone https://github.com/VL-code13/hop.git
cd hop
```

**2. Установите зависимости через Poetry:**

```bash
poetry install
```

Poetry создаст `.venv/` в проекте и установит все зависимости из `poetry.lock`. Dev-пакеты (`pytest`, `ruff`, `mypy`)
тоже установятся — они в группе `dev`.

**3. Создайте `.env` (опционально — `development.py` подставляет дефолты):**

```bash
cp .env.example .env
```

Отредактируйте `DJANGO_SECRET_KEY` — можно сгенерировать:

```bash
poetry run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

**4. Примените миграции и создайте администратора:**

```bash
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
```

**5. Запустите сервер:**

```bash
poetry run python manage.py runserver
```

Приложение: http://127.0.0.1:8000/
GraphiQL (интерактивный GraphQL-клиент): http://127.0.0.1:8000/graphql/

> **Совет:** активируйте виртуальное окружение Poetry командой `poetry shell` — тогда `python`, `pytest`, `ruff` будут
> работать без префикса `poetry run`.

### Вариант B: Docker Compose (PostgreSQL + WhiteNoise)

**1. Подготовьте `.env`:**

```bash
cp .env.example .env
# Для PostgreSQL задайте:
#   DJANGO_SETTINGS_MODULE=config.settings.prod
#   POSTGRES_HOST=db
```

**2. Запустите контейнеры:**

```bash
docker compose up --build -d
```

**3. Примените миграции и соберите статику:**

```bash
docker compose exec web poetry run python manage.py migrate
docker compose exec web poetry run python manage.py createsuperuser
docker compose exec web poetry run python manage.py collectstatic --noinput
```

**Точки входа:**

| Сервис                     | URL                                |
|----------------------------|------------------------------------|
| Каталог магазина           | http://localhost:8080/             |
| Админ-панель с аналитикой  | http://localhost:8080/admin/       |
| REST API                   | http://localhost:8080/api/         |
| Swagger UI                 | http://localhost:8080/api/docs/    |
| ReDoc                      | http://localhost:8080/api/redoc/   |
| **GraphiQL (GraphQL IDE)** | **http://localhost:8080/graphql/** |

---

## Переменные окружения (.env)

| Переменная               | Обязательна | По умолчанию                              | Назначение                                                                 |
|--------------------------|:-----------:|-------------------------------------------|----------------------------------------------------------------------------|
| `DJANGO_SECRET_KEY`      |   **Да**    | —                                         | Секретный ключ. Без него — `ImproperlyConfigured`.                         |
| `DJANGO_SETTINGS_MODULE` |     Нет     | `config.settings.development`             | Какой конфиг использовать: `development`, `prod`, `ci`, `test`.            |
| `DJANGO_DEBUG`           |     Нет     | `True` (dev) / `False` (prod)             | В `prod.py` guard: `DEBUG=True` разрешён только с `ALLOW_DEBUG_IN_PROD=1`. |
| `DJANGO_ALLOWED_HOSTS`   |     Нет     | `*` (dev) / `example.com` (prod)          | Список доверенных хостов через запятую.                                    |
| `POSTGRES_DB`            | Для prod/ci | `hopbarley` / `test_db`                   | Имя базы.                                                                  |
| `POSTGRES_USER`          | Для prod/ci | `user` / `postgres`                       | Пользователь БД.                                                           |
| `POSTGRES_PASSWORD`      | Для prod/ci | `p@ssword123` / `postgres`                | Пароль.                                                                    |
| `POSTGRES_HOST`          | Для prod/ci | `db` / `localhost`                        | Хост PostgreSQL.                                                           |
| `POSTGRES_PORT`          |     Нет     | `5432`                                    | Порт PostgreSQL.                                                           |
| `EMAIL_BACKEND`          |     Нет     | `console`                                 | Backend отправки писем. В CI — `locmem`.                                   |
| `DEFAULT_FROM_EMAIL`     |     Нет     | `Hop & Barley <noreply@hopandbarley.com>` | Адрес отправителя.                                                         |

---

## Реализованная бизнес-логика

### Каталог товаров (`products`)

- Расчёт складской доступности через свойство `in_stock`.
- Полнотекстовый поиск по имени и описанию (`?q=`).
- Диапазонная фильтрация цен и категорий.
- Сортировка: `newest`, `price_asc`, `price_desc`, `popular`, `name`. Белый список `SORT_MAPPING` защищает от
  SQL-инъекций через `?sort=`.
- Пагинация по 9 товаров.
- Сервисный слой `products/services.py` — вся логика фильтрации в чистой функции `get_catalog_queryset()`.

### Сессионная корзина и оформление заказа (`orders`)

- Корзина работает для анонимных гостей и авторизованных пользователей.
- Жёсткий контроль остатка: `Cart.add()` возвращает `False`, если запрос превышает `Product.stock`.
- **Атомарное списание остатков** (защита от overselling):

  ```python
  updated = Product.objects.filter(
      id=p.id,
      stock__gte=qty,
  ).update(stock=F('stock') - qty, updated_at=timezone.now())
  if not updated:
      raise ValidationError('Остаток изменился. Повторите попытку.')
  ```

  Это даёт защиту на **двух уровнях**:
    1. `select_for_update()` блокирует строки на PostgreSQL.
    2. `filter(stock__gte=qty).update(F(...))` — атомарный SQL-запрос, который работает даже на SQLite (где
       `select_for_update` — no-op).

- **Snapshot цены** в `OrderItem.price`.
- Email-уведомления покупателю и администраторам с `logger.exception` при сбое SMTP.

### Отзывы и рейтинги (`reviews`)

- **Двухфакторная проверка**: оставить отзыв (1–5 звёзд) может только авторизованный клиент, ранее купивший и оплативший
  (`PAID`) или получивший (`DELIVERED`) товар.
- `UniqueConstraint(fields=['product', 'user'])` на уровне БД — повторный отзыв невозможен.
- **DRY-подход**: бизнес-правило вынесено в `reviews/services.py:get_review_permissions()` и **переиспользуется** в
  web-view и API-сериализаторе.

### Сервис эмуляции платежей (`payments`)

- Изолированный `PaymentService`:
    - проверяет принадлежность заказа клиенту через `select_for_update().get(id=..., user=user)` — закрывает IDOR
      архитектурно;
    - валидирует статус (`Pending` → `Paid`);
    - ведёт журнал транзакций с UUID-PK.

- **Трёхуровневая защита от двойной оплаты**:
    1. Проверка статуса в `get_payable_order`.
    2. Проверка статуса под `select_for_update` в `process_payment`.
    3. `UniqueConstraint(fields=['order'], condition=Q(status='SUCCESS'))` на уровне БД.

### Пользователи и безопасность (`users`)

- **Кастомный бэкенд** `EmailOrUsernameModelBackend`: вход по `username` или `email`.
- **Валидация пароля** через `validate_password` — все `AUTH_PASSWORD_VALIDATORS` работают.
- **Нормализация телефона** через `users/phone.py`: любая форма ввода → `+7XXXXXXXXXX` в БД.
- **Экранирование email** через `format_html` вместо `mark_safe` (защита от XSS).
- **Soft Delete** + **реактивация через сброс пароля**.

---

## Спецификация REST API

Базовый путь: `/api/`. Полная документация — в Swagger UI (`/api/docs/`).

| Метод  | URL                           | Права доступа | Назначение                                    |
|--------|-------------------------------|---------------|-----------------------------------------------|
| POST   | `/api/users/register/`        | Любой         | Регистрация нового покупателя                 |
| POST   | `/api/users/login/`           | Любой         | Получение JWT-пары (access + refresh)         |
| POST   | `/api/token/refresh/`         | Refresh Token | Ротация access-токена                         |
| GET    | `/api/products/`              | Любой         | Каталог с пагинацией, фильтрами, поиском      |
| GET    | `/api/products/{id}/`         | Любой         | Детальная карточка товара                     |
| GET    | `/api/products/{id}/reviews/` | Любой         | Список отзывов товара                         |
| POST   | `/api/products/{id}/reviews/` | Bearer JWT    | Добавление отзыва (проверка покупки)          |
| GET    | `/api/cart/`                  | Session / JWT | Просмотр корзины                              |
| POST   | `/api/cart/`                  | Session / JWT | Добавление позиции                            |
| PATCH  | `/api/cart/`                  | Session / JWT | Изменение количества                          |
| DELETE | `/api/cart/`                  | Session / JWT | Очистка корзины                               |
| POST   | `/api/orders/`                | Bearer JWT    | Создание заказа (атомарное списание остатков) |
| GET    | `/api/orders/`                | Bearer JWT    | Список заказов пользователя                   |
| GET    | `/api/orders/{id}/`           | Bearer JWT    | Детали своего заказа                          |
| DELETE | `/api/orders/{id}/`           | Bearer JWT    | Отмена заказа (возврат остатков)              |

---

## Примеры запросов с JWT

### 1. Получение пары токенов (вход)

```bash
curl -X POST http://localhost:8080/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "brewer@example.com", "password": "StrongPass123!"}'
```

Ответ `200 OK`:

```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 2. Сохранение access-токена в переменную

```bash
ACCESS=$(curl -s -X POST http://localhost:8080/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "brewer@example.com", "password": "StrongPass123!"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access'])")
```

### 3. Публичный запрос (каталог)

```bash
curl "http://localhost:8080/api/products/?min_price=300&max_price=600&ordering=price"
```

### 4. Добавление товара в корзину (JWT)

```bash
curl -X POST http://localhost:8080/api/cart/ \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

### 5. Создание заказа

```bash
curl -X POST http://localhost:8080/api/orders/ \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{
    "shipping_address": "г. Москва, ул. Пивоваров, д. 10, кв. 5",
    "payment_method": "card"
  }'
```

Ответ `201 Created`:

```json
{
  "id": 42,
  "user": "brewer@example.com",
  "status": "pending",
  "total_price": "1100.00",
  "items": [
    {
      "product": 1,
      "product_name": "Хмель Citra (100г)",
      "price": "550.00",
      "quantity": 2
    }
  ]
}
```

### 6. Обновление access-токена

```bash
curl -X POST http://localhost:8080/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

---

## GraphQL API

Эндпоинт `/graphql/` реализован на **Strawberry GraphQL** — type-safe альтернативе Graphene с нативной интеграцией с
Django ORM через `strawberry-graphql-django`. Раздел 3.9 ТЗ (бонус).

### Возможности

Аналитический слой по трём направлениям:

- **Заказы**: выручка, количество, средний чек, уникальные клиенты, тренды по интервалам.
- **Продукты**: популярные товары (по продажам), низкие остатки, товары с нулевым остатком.
- **Пользователи**: активность (новые / активные / повторные), динамика повторных покупок, LTV конкретного клиента.

Дополнительно:

- `health` — публичная проверка живости эндпоинта.
- `me` — публичный резолвер профиля текущего пользователя.

### Архитектура

- `config/graphql/schema.py` — корневая схема, собирает Query-классы из доменов.
- `config/graphql/context.py` — `GraphQLContext` (доступ к `request.user` и per-request кешу) + кастомный
  `HopBarleyGraphQLView`, переопределяющий `get_context`.
- `config/graphql/middleware.py` — `GraphQLJWTAuthMiddleware`, читает JWT из заголовка `Authorization: Bearer ...` для
  путей `/graphql/`.
- `config/graphql/permissions.py` — декоратор `@staff_only`, бросает `GraphQLError` с `extensions.code`
  (`UNAUTHENTICATED` / `FORBIDDEN`).
- `config/graphql/cache.py` — декоратор `@cache_metric`, кеширует результаты тяжёлых аналитических резолверов с
  per-resolver TTL.
- `<app>/graphql/types.py` — GraphQL-типы, привязанные к Django-моделям через `@strawberry_django.type`.
- `<app>/graphql/analytics.py` — резолверы аналитических запросов.

### Аутентификация

Используется **тот же JWT** от `rest_framework_simplejwt`, что и для REST API. После логина через `/api/users/login/`
клиент передаёт токен в заголовке:

```
Authorization: Bearer <access_token>
```

`GraphQLJWTAuthMiddleware` перехватывает запросы к `/graphql/`, проверяет подпись и срок действия, и подставляет
`request.user`. Если токен отсутствует или невалиден — пользователь остаётся `AnonymousUser`.

### Права доступа

| Резолвер                                                       |       Гость        | Обычный юзер | Staff |
|----------------------------------------------------------------|:------------------:|:------------:|:-----:|
| `health`                                                       |         ✅         |      ✅      |  ✅   |
| `me`                                                           |       `null`       |      ✅      |  ✅   |
| `orderMetrics`, `orderTrends`                                  | ❌ UNAUTHENTICATED | ❌ FORBIDDEN |  ✅   |
| `popularProducts`, `lowStockProducts`, `outOfStockProducts`    |         ❌         |      ❌      |  ✅   |
| `userActivity`, `repeatPurchaseTrend`, `customerLifetimeValue` |         ❌         |      ❌      |  ✅   |

Проверка прав выполняется в декораторе `@staff_only` — **до** тела резолвера, поэтому неавторизованные запросы не
нагружают БД.

### Примеры запросов

#### Проверка живости

```graphql
{
  health
}
```

#### Дашборд заказов

```graphql
query OrdersDashboard {
  orderMetrics(dateFrom: "2026-08-01", dateTo: "2026-09-01") {
    totalRevenue
    orderCount
    averageOrderValue
    uniqueCustomers
    cancelledCount
  }

  orderTrends(
    dateFrom: "2026-08-01"
    dateTo: "2026-09-01"
    interval: "week"
  ) {
    revenue { period value }
    orders { period value }
    averageOrderValue { period value }
  }
}
```

#### Товарная аналитика

```graphql
query ProductsAnalytics {
  popularProducts(limit: 5) {
    product { id name price }
    unitsSold
    revenue
  }

  lowStockProducts(threshold: 10) {
    product { id name stock }
    stock
    deficit
  }

  outOfStockProducts {
    product { id name }
    stock
  }
}
```

#### Пользовательская аналитика

```graphql
query UsersAnalytics {
  userActivity(dateFrom: "2026-08-01") {
    newUsers
    activeBuyers
    repeatBuyers
    repeatPurchaseRate
    ordersPerBuyer
  }

  repeatPurchaseTrend(interval: "month") {
    period
    value
  }

  customerLifetimeValue(userId: "42")
}
```

#### Текущий пользователь

```graphql
{
  me {
    id
    username
    email
  }
}
```

### Как передать токен в GraphiQL

1. Открой http://127.0.0.1:8000/graphql/
2. Получите access-токен через REST: `POST /api/users/login/`
3. В GraphiQL внизу страницы раскройте панель **«Headers»**
4. Вставьте:

```json
{
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."
}
```

### Проверка через curl

```bash
# Health (без токена)
curl -X POST http://localhost:8000/graphql/ \
  -H "Content-Type: application/json" \
  -d '{"query": "{ health }"}'

# Аналитика (staff-токен)
curl -X POST http://localhost:8000/graphql/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS" \
  -d '{"query": "{ orderMetrics { totalRevenue orderCount } }"}'
```

### Производительность

- **Все агрегаты считаются на стороне БД** — `Sum`, `Count`, `Avg`, `Trunc`, `TruncDate/Week/Month`. Никаких питоновских
  переборов заказов.
- **`DjangoOptimizerExtension`** автоматически применяет `select_related` / `prefetch_related` там, где резолверы читают
  связанные поля.
- **Индексы под аналитику** — составные индексы по `(status, paid_at)` и `(user, created_at)` для быстрой фильтрации.
- **Кеширование метрик** через `@cache_metric` с per-resolver TTL:
    - `out_of_stock_products` — 60 сек (критично для UX),
    - `low_stock_products` — 120 сек,
    - `order_metrics`, `order_trends`, `user_activity`, `customer_lifetime_value` — 300 сек,
    - `popular_products`, `repeat_purchase_trend` — 600 сек.

### Кеширование

Кеширование аналитических метрик реализовано в `config/graphql/cache.py` через декоратор `@cache_metric`. Порядок
декораторов строго:

```python
@strawberry.field
@staff_only  # проверка прав — ДО кеша
@cache_metric(...)  # кеш — только после успешной проверки
def resolver(...): ...
```

Если поменять местами — обычный пользователь получит данные из кеша в обход `@staff_only`. Это **дыра в безопасности**,
покрыта регрессионным тестом `test_permissions_checked_before_cache`.

**Backend кеша** — `django.core.cache`, дефолт — `LocMemCache` (in-memory). Для продакшена достаточно добавить в
`CACHES`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL'),
    },
}
```

Резолверы и декоратор при этом не меняются.

**Инвалидация.** Сейчас её нет — метрики «догоняют» данные через TTL. Если понадобится мгновенная актуальность —
сбрасывайте кеш через `django.core.cache.cache.clear()` или сигналы `post_save` на `Order`.

---

## Аутентификация и безопасность

### Web UI (браузер)

- Сессионная аутентификация Django (`SessionAuthentication`).
- CSRF-токены во всех формах POST.
- `SESSION_COOKIE_AGE = 30 дней`.

### REST API (клиенты)

- JWT через `djangorestframework-simplejwt`.
- Заголовок: `Authorization: Bearer <access_token>`.

**Жизненный цикл токенов:**

| Параметр                   | Значение |
|----------------------------|----------|
| `ACCESS_TOKEN_LIFETIME`    | 60 минут |
| `REFRESH_TOKEN_LIFETIME`   | 7 дней   |
| `ROTATE_REFRESH_TOKENS`    | `True`   |
| `BLACKLIST_AFTER_ROTATION` | `False`  |

### GraphQL (аналитика)

- Использует **тот же JWT**, что и REST API — единая точка выпуска токенов.
- Токен передаётся в стандартном заголовке `Authorization: Bearer ...`.
- Отдельного механизма аутентификации в GraphQL нет — `GraphQLJWTAuthMiddleware` переиспользует `AccessToken` от
  SimpleJWT.
- Эндпоинт `/graphql/` объявлен как `csrf_exempt` — это безопасно, потому что JWT не полагается на cookies, и CSRF-атака
  технически невозможна.

---

## OpenAPI и интерактивная документация

Схема генерируется `drf-spectacular`:

| Сервис                     | URL             |
|----------------------------|-----------------|
| Swagger UI                 | `/api/docs/`    |
| ReDoc                      | `/api/redoc/`   |
| OpenAPI YAML               | `/api/schema/`  |
| **GraphiQL (GraphQL IDE)** | **`/graphql/`** |

Проверка схемы на валидность:

```bash
poetry run python manage.py spectacular --validate
```

---

## Тестирование и контроль качества

### Запуск тестов

**Сценарий 1 — быстро, на SQLite in-memory:**

```bash
poetry run pytest --ds=config.settings.test
```

**Сценарий 2 — как в CI, на PostgreSQL:**

```bash
# 1. Поднять PostgreSQL
docker compose up -d db

# 2. Прогнать тесты
poetry run pytest --ds=config.settings.ci --create-db --migrations
```

**Сценарий 3 — только GraphQL-тесты, без coverage:**

```bash
poetry run pytest tests/graphql/ --ds=config.settings.test --no-cov -v
```

**Сценарий 4 — с полным coverage-отчётом:**

```bash
poetry run pytest --ds=config.settings.test \
  --cov=. --cov-report=term-missing --cov-report=html
```

HTML-отчёт: `htmlcov/index.html`.

### Покрытие

Целевой порог — **70%** (`--cov-fail-under=70`).

Декларативные файлы (`apps.py`, `migrations`, `wsgi.py`, `asgi.py`, `urls.py`, `admin.py`, `conftest.py`,
`*/graphql/types.py`, `*/graphql/__init__.py`) исключены через `.coveragerc`.

### Структура тестов

- **Модульные тесты приложения** — в `<app>/tests.py`.
- **Сервисные тесты** — в `<app>/tests_services.py` (без HTTP-клиента).
- **Интеграционные GraphQL-тесты** — в `tests/graphql/`:
    - `test_permissions.py` — аноним / FORBIDDEN / staff / health.
    - `test_order_analytics.py` — `orderMetrics`, `orderTrends`.
    - `test_product_analitics.py` — `lowStockProducts`, `popularProducts`, `outOfStockProducts`.
    - `test_user_queries.py` — `me`, аналитика пользователей.
    - `test_cache.py` — кеширование метрик и порядок проверки прав относительно кеша.
- **Фикстуры** — в глобальном `conftest.py`. Включают:
    - `staff_user` — staff без superuser (для проверки аналитики).
    - `user_token`, `staff_token`, `admin_token` — JWT для запросов к `/graphql/`.
    - `_clear_cache` (autouse) — сбрасывает кеш до и после каждого теста. Без неё `LocMemCache` живёт между тестами и
      ломает изоляцию.

### Статический анализ

```bash
# Линтер
poetry run ruff check .

# Форматирование
poetry run ruff format --check .

# Типизация (django-stubs)
poetry run mypy .
```

### Управление зависимостями

```bash
# Добавить основную зависимость
poetry add <package>

# Добавить dev-зависимость
poetry add --group dev <package>

# Удалить
poetry remove <package>
poetry remove --group dev <package>

# Обновить lock-файл после ручной правки pyproject.toml
poetry lock

# Показать дерево зависимостей
poetry show --tree

# Показать только основные / только dev
poetry show --only main
poetry show --only dev
```

---

## CI/CD

GitHub Actions workflow — [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — запускается на push и pull request в
ветку `dev_3st_week`.

**Шаги пайплайна:**

1. **Checkout** и **Setup Python 3.12** с кэшем Poetry.
2. **Install Poetry** — `pipx install poetry`.
3. **Install dependencies** — `poetry install --no-interaction`.
4. **Ruff check** — `poetry run ruff check .`.
5. **Ruff format check** — `poetry run ruff format --check .`.
6. **Mypy** — `poetry run mypy .`.
7. **Django system check** — `poetry run python manage.py check`.
8. **Check migrations** — `poetry run python manage.py makemigrations --check --dry-run`.
9. **Run migrations** на PostgreSQL 16 (service container).
10. **Pytest** — `poetry run pytest --create-db --migrations --cov-fail-under=70`.

**Локальная симуляция CI:**

```bash
docker compose up -d db

export DJANGO_SETTINGS_MODULE=config.settings.ci
export DJANGO_SECRET_KEY=ci-secret-key-that-is-long-enough-for-hmac-sha256
export POSTGRES_DB=test_db POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost POSTGRES_PORT=5432

poetry run ruff check . && \
poetry run ruff format --check . && \
poetry run mypy . && \
poetry run python manage.py check && \
poetry run python manage.py makemigrations --check --dry-run && \
poetry run python manage.py migrate --noinput && \
poetry run pytest --create-db --migrations --cov-fail-under=70
```

---

## Панель администратора и аналитика

Кастомный `HopBarleyAdminSite` доступен по адресу `/admin/` и включает инструменты мониторинга (раздел 3.6 ТЗ):

- **Аналитический дашборд**: выручка по оплаченным заказам (`PAID`, `SHIPPED`, `DELIVERED`), счётчик заказов в
  обработке, число активных клиентов и товаров.
- **Складской контроль**: список позиций с критическим остатком (< 5 шт.).
- **Кастомные actions** в `OrderAdmin`: `mark_as_paid`, `mark_as_shipped`, `show_revenue`.
- **Массовые действия** в `ProductAdmin`: `make_active`, `make_inactive`.
- **Финансовые транзакции read-only**: `PaymentTransactionAdmin` запрещает создание и редактирование.
- **Кастомная страница удаления товара**: товары с историей заказов не удаляются, а деактивируются через `delete_view` +
  `has_delete_permission`.

Аналогичные метрики доступны через GraphQL-эндпоинт `/graphql/` — для интеграции с внешними дашбордами (Grafana,
Metabase, BI-системы).

---
## Pre-commit hooks

Проект использует [`pre-commit`](https://pre-commit.com/) для автоматической проверки кода перед коммитом. Хуки запускаются **локально** и **до** push — это ловит мелочи (trailing whitespace, order импортов, форматирование) без итерации с CI.

### Что проверяется

| Хук | Когда | Что делает |
|-----|-------|------------|
| `trailing-whitespace` | commit | Убирает пробелы в конце строк |
| `end-of-file-fixer` | commit | Гарантирует `\n` в конце файла |
| `check-yaml` / `check-toml` | commit | Проверяет синтаксис конфигов |
| `check-added-large-files` | commit | Блокирует файлы > 500 KB |
| `check-merge-conflict` | commit | Ищет маркеры `<<<<<<<` |
| `detect-private-key` | commit | Не даёт закоммитить ключи |
| `ruff` | commit | Линтер с автофиксом (`--fix`) |
| `ruff-format` | commit | Форматтер |
| `mypy` | push | Статическая типизация (через pre-push hook) |
| `pytest` | push | Тесты (через pre-push hook) |

### Установка

Хуки ставятся автоматически после `poetry install`:

```bash
poetry run pre-commit install
---
## Ограничения и известные компромиссы

### Совместимость с БД

- **`select_for_update()` не работает на SQLite.** Django молча игнорирует этот метод — реальной блокировки строк не
  происходит. Защита от overselling работает за счёт `filter(stock__gte=qty).update(F('stock') - qty)`, который атомарен
  на любой БД.
- **Разная семантика `NULL`** в сортировках: SQLite и PostgreSQL по-разному упорядочивают `NULL` при `ORDER BY DESC`.
- **Регистронезависимый поиск** через `icontains` на SQLite не учитывает регистр кириллицы. На PostgreSQL работает
  корректно.

### Асинхронность и фоновые задачи

- **Email-уведомления отправляются синхронно** внутри транзакции чекаута. В продакшене это стоит вынести в Celery.
- **Нет Celery и Redis** — фоновых задач нет.

### GraphQL

- Раздел 3.9 ТЗ (бонус) **реализован** на Strawberry GraphQL.
- Аналитические резолверы защищены `@staff_only` — обычные пользователи получают `FORBIDDEN`, гости — `UNAUTHENTICATED`.
- **Кеширование аналитических метрик** реализовано через декоратор `config/graphql/cache.py:@cache_metric`. Backend по
  умолчанию — `LocMemCache` (in-memory, подходит для dev и одного воркера). Для продакшена достаточно добавить в
  `CACHES` backend `RedisCache` — код резолверов менять не нужно.
- **TTL для метрик разный**: `out_of_stock` — 60 сек (критично для UX), `low_stock` — 120 сек, `popular_products` и
  `repeat_purchase_trend` — 600 сек (статистика за всё время меняется медленно), остальные — 300 сек.
- **Инвалидации по сигналам нет** — метрики «догоняют» данные через TTL. При необходимости — `cache.clear()` вручную или
  сигнал `post_save` на `Order`.
- **Подписки (subscriptions) не реализованы** — требуют Django Channels, что выходит за рамки бонусного задания.
- **Мутации для CRUD в GraphQL отсутствуют** — весь CRUD закрыт через REST API. Дублировать его смысла нет.

### Хранение файлов

- Изображения товаров и аватары хранятся в `FileSystemStorage` (локально).
- Для продакшена рекомендуется S3-совместимое хранилище (`django-storages`).

### Безопасность

- `SECRET_KEY` в Docker Compose берётся из `.env` — для продакшена нужен секрет-менеджер (Vault, AWS Secrets Manager).
- `BLACKLIST_AFTER_ROTATION = False` — украденный refresh-токен можно использовать параллельно с новым.
- `SECURE_HSTS_*`, `SECURE_PROXY_SSL_HEADER` не заданы — при деплое за nginx их надо добавить в `prod.py`.

### Платежи

- **Платёжный шлюз эмурован** (`simulate_success=True`). Реальной интеграции со Stripe/YooKassa/CloudPayments нет.

### Тесты

- Покрытие тестами сфокусировано на бизнес-логике и моделях. Views, сериализаторы и API-контроллеры покрыты частично.
- GraphQL-тесты покрывают права доступа, ключевые метрики и кеш.
- Нет тестов на race condition (`select_for_update`) — сложно воспроизвести в `TestCase`.

### Инфраструктура

- `docker-compose.yaml` собран для учебного запуска. По умолчанию `web`-контейнер использует
  `config.settings.development` (SQLite), если `DJANGO_SETTINGS_MODULE` не переопределён.
- Медиа-файлы в Docker не сохраняются между перезапусками (volume не настроен).

---

## Лицензия

Учебный проект. Свободно используйте код для обучения и портфолио.

---

**Сделано с ❤️ для сообщества домашних пивоваров.**
