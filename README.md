# Hop & Barley — интернет-магазин товаров для крафтового пивоварения

Полнофункциональный веб-сервис на Django 6.1 и Django REST Framework для онлайн-продажи сырья, ингредиентов, рецептурных наборов и оборудования для домашнего пивоварения.

Архитектура построена по принципу разделения ответственности («тонкие контроллеры, толстый слой сервисов/сериализаторов»). Использует:

- **атомарное списание остатков** через `F()`-выражения и `filter(stock__gte=qty).update(...)` — защита от overselling даже там, где `select_for_update()` не работает;
- **гибридную сессионную корзину** — работает для анонимных и авторизованных пользователей;
- **JWT-аутентификацию** через `djangorestframework-simplejwt`;
- **двухуровневую защиту от двойной оплаты** — `select_for_update` + `UniqueConstraint` на БД;
- **нормализацию телефонов** через `users/phone.py` — единый формат `+7XXXXXXXXXX` в БД;
- **DRY бизнес-правило отзывов** — «только после покупки» живёт в `reviews/services.py` и переиспользуется в web и API;
- **кастомную аналитическую панель** с дашбордом, складским контролем и журналом заказов;
- **GraphQL-эндпоинт** `/graphql/` на Strawberry — единая точка для аналитических запросов по заказам, товарам и пользователям;
- **кеширование аналитических метрик** через Redis — общий кеш для всех воркеров gunicorn, per-resolver TTL;
- **фоновые задачи через Celery** — email-уведомления не блокируют чекаут, retry при сбое SMTP;
- **pre-commit hooks** для автоматического `ruff`, `ruff-format`, `mypy` и `pytest` перед коммитом и push;
- **Makefile** со шорткатами для типовых команд (`make ci`, `make test`, `make run`, `make worker`);
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
- [Pre-commit hooks](#pre-commit-hooks)
- [Makefile](#makefile)
- [Ограничения и известные компромиссы](#ограничения-и-известные-компромиссы)

---

## Технологический стек

| Категория | Технология / Библиотека | Назначение |
|-----------|------------------------|------------|
| Язык | Python 3.12 | Runtime |
| Менеджер зависимостей | **Poetry 2.x** | Lockfile, изоляция venv, разделение main/dev |
| Бэкенд-платформа | Django 6.1.1 | Веб-ядро, ORM, маршрутизация, шаблонизатор, сигналы |
| REST API | Django REST Framework 3.18 | Сериализация, валидация запросов, ViewSets, permissions |
| **GraphQL** | **Strawberry GraphQL 0.327 + strawberry-graphql-django 0.89** | **Аналитический эндпоинт `/graphql/`** |
| JWT-авторизация | djangorestframework-simplejwt 5.5.1 | Выпуск, проверка и ротация Access / Refresh токенов |
| Кеш | Redis 7 + `django.core.cache.RedisCache` | Кеширование аналитических метрик GraphQL |
| **Фоновые задачи** | **Celery 5.6 + Redis broker** | **Email-уведомления, retry, отложенные операции** |
| Схема OpenAPI | drf-spectacular 0.30.0 | Генерация OpenAPI 3.0, интерактивных Swagger UI и ReDoc |
| Статические файлы | WhiteNoise 6.12 | Раздача сжатой кэшируемой статики с манифестным хешированием |
| СУБД (Production) | PostgreSQL 16 + psycopg 3.3 | Продакшн-база с поддержкой строгой изоляции транзакций |
| СУБД (Development) | SQLite | Встроенная база для ускоренной локальной разработки |
| Тестирование | pytest 9.1 + pytest-django + pytest-cov | Набор из 72+ тестов с автоматическим замером покрытия |
| Статический анализ | Ruff 0.16 + Mypy 1.13 + django-stubs | Линтинг по PEP 8 и статическая типизация |
| Контроль качества | pre-commit 4.x | Git-хуки для ruff, mypy, pytest |
| Автоматизация | Makefile | Шорткаты для типовых команд |
| Контейнеризация | Docker + Docker Compose | Изоляция сервисов (web + db + redis + worker) |

---

## Архитектурная структура проекта

```text
hop-and-barley/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions: ruff, mypy, pytest на PostgreSQL
├── config/                     # Настройки проекта
│   ├── settings/
│   │   ├── base.py             # Базовые параметры, JWT, WhiteNoise, DRF, Strawberry, CACHES, CELERY
│   │   ├── development.py      # SQLite, DEBUG=True, локальная разработка
│   │   ├── prod.py             # PostgreSQL, Redis (fail-fast), security-настройки
│   │   ├── test.py             # SQLite in-memory, LocMemCache, CELERY_TASK_ALWAYS_EAGER
│   │   └── ci.py               # PostgreSQL, Redis, CELERY_TASK_ALWAYS_EAGER, locmem email
│   ├── celery.py               # Celery app + autodiscover_tasks
│   ├── __init__.py             # экспорт celery_app — точка входа @shared_task
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
│   ├── models.py               # Category (иерархия), Product
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
│   ├── tasks.py                # Celery-задачи: send_order_confirmation, notify_admins_new_order
│   ├── forms.py                # OrderCreateForm + нормализация телефона
│   ├── context_processors.py   # Инъекция cart в шаблоны
│   ├── admin.py                # Обработка заказов, аналитика, actions
│   ├── graphql/
│   │   ├── types.py            # OrderType, OrderItemType, OrderMetrics, TrendPoint
│   │   └── analytics.py        # orderMetrics, orderTrends
│   └── tests.py                # Тесты корзины, списания остатков и email
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
├── .dockerignore               # Исключения для Docker build context
├── .env.example                # Шаблон переменных окружения
├── .pre-commit-config.yaml     # Конфигурация pre-commit hooks
├── docker-compose.yaml         # Сервисы: db (PostgreSQL) + redis + worker + web
├── Dockerfile                  # Multi-stage сборка на Poetry
├── pyproject.toml              # Poetry + Ruff + Mypy (единый конфиг)
├── poetry.lock                 # Зафиксированные версии зависимостей
├── pytest.ini                  # Конфигурация pytest
├── conftest.py                 # Глобальные pytest-фикстуры (JWT, _clear_cache)
├── Makefile                    # Шорткаты для типовых команд
├── manage.py
└── README.md
```

---

## Быстрый старт

### Требования

| Инструмент | Версия | Установка |
|------------|--------|-----------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Poetry | 2.0+ | `pipx install poetry` или `curl -sSL https://install.python-poetry.org \| python3 -` |
| PostgreSQL | 16+ | Системный или через Docker (`docker compose up -d db`) |
| Redis | 7+ | Системный (`apt install redis-server`) или через Docker |
| Docker | 24+ (опционально) | [docs.docker.com](https://docs.docker.com/get-docker/) |

### Вариант A: Локальная разработка

**1. Клонируйте репозиторий:**

```bash
git clone https://github.com/VL-code13/hop.git
cd hop
```

**2. Установите зависимости и pre-commit hooks:**

```bash
make install
```

Или вручную:

```bash
poetry install
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push
```

**3. Создайте `.env`:**

```bash
cp .env.example .env
# Отредактируйте DJANGO_SECRET_KEY:
poetry run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

**4. Поднимите PostgreSQL и Redis:**

```bash
make up           # PostgreSQL (системный, если есть; иначе — Docker через pg_isready)
make up-redis     # Redis в Docker (если системного нет)
```

Или вручную:

```bash
# Если системные сервисы уже работают — они и будут использованы.
# Если нет — поднять Docker-контейнеры:
docker compose up -d db redis
```

> **Важно:** `make up` идемпотентен — если системный PostgreSQL уже слушает `localhost:5432` (проверяется через `pg_isready`), Docker-контейнер не поднимается. Это страхует от `address already in use` на машинах с системными сервисами. То же для `make up-redis` (`redis-cli ping`).

**5. Примените миграции и создайте администратора:**

```bash
make migrate
poetry run python manage.py createsuperuser
```

**6. Запустите сервер:**

```bash
make run
```

**7. В отдельном терминале — запустите Celery worker:**

```bash
make worker
```

Или вручную:

```bash
poetry run celery -A config worker -l info
```

> **Важно:** без воркера email-уведомления не отправятся — задачи будут копиться в Redis. Для локальной разработки без воркера можно поднять `CELERY_TASK_ALWAYS_EAGER=True` в `.env`, но лучше — запустить воркер.

**Точки входа:**

| Сервис | URL / где смотреть |
|--------|---------------------|
| Каталог магазина | http://127.0.0.1:8000/ |
| Админ-панель с аналитикой | http://127.0.0.1:8000/admin/ |
| REST API | http://127.0.0.1:8000/api/ |
| Swagger UI | http://127.0.0.1:8000/api/docs/ |
| ReDoc | http://127.0.0.1:8000/api/redoc/ |
| **GraphiQL (GraphQL IDE)** | **http://127.0.0.1:8000/graphql/** |
| **Celery worker** | **Логи в терминале (`make worker`)** |

### Вариант B: Docker Compose

**1. Подготовьте `.env`:**

```bash
cp .env.example .env
# Для PostgreSQL задайте:
#   DJANGO_SETTINGS_MODULE=config.settings.prod
#   POSTGRES_HOST=db
#   REDIS_URL=redis://redis:6379/0
#   CELERY_BROKER_URL=redis://redis:6379/1
#   CELERY_RESULT_BACKEND=redis://redis:6379/2
```

**2. Запустите контейнеры:**

```bash
docker compose up --build -d
```

Поднимаются 4 сервиса: `db`, `redis`, `web`, `worker`.

**3. Примените миграции и соберите статику:**

```bash
docker compose exec web poetry run python manage.py migrate
docker compose exec web poetry run python manage.py createsuperuser
docker compose exec web poetry run python manage.py collectstatic --noinput
```

**Точки входа:** те же, что выше, только порт `8080` вместо `8000` (см. `docker-compose.yaml`).

### Шорткаты через Makefile

Все типовые команды обёрнуты в `Makefile`. Полный список — `make help`.

```bash
make install         # установить зависимости и pre-commit hooks
make run             # запустить dev-сервер
make worker          # запустить Celery worker
make test            # быстрые тесты на SQLite
make test-graphql    # только тесты GraphQL
make test-orders     # только тесты заказов (включая email)
make lint            # проверка ruff + mypy
make format          # автоформатирование
make ci              # полная симуляция CI перед push
make up              # PostgreSQL (системный или Docker)
make up-redis        # Redis в Docker (если системного нет)
make up-all          # весь стек в контейнерах
make flush-cache     # очистить кеш
```

---

## Переменные окружения (.env)

| Переменная | Обязательна | По умолчанию | Назначение |
|------------|:-----------:|--------------|------------|
| `DJANGO_SECRET_KEY` | **Да** | — | Секретный ключ. Без него — `ImproperlyConfigured`. |
| `DJANGO_SETTINGS_MODULE` | Нет | `config.settings.development` | Какой конфиг использовать: `development`, `prod`, `ci`, `test`. |
| `DJANGO_DEBUG` | Нет | `True` (dev) / `False` (prod) | В `prod.py` guard: `DEBUG=True` разрешён только с `ALLOW_DEBUG_IN_PROD=1`. |
| `DJANGO_ALLOWED_HOSTS` | Нет | `*` (dev) / `example.com` (prod) | Список доверенных хостов через запятую. |
| `POSTGRES_DB` | Для prod/ci | `hopbarley` / `test_db` | Имя базы. |
| `POSTGRES_USER` | Для prod/ci | `user` / `postgres` | Пользователь БД. |
| `POSTGRES_PASSWORD` | Для prod/ci | `p@ssword123` / `postgres` | Пароль. |
| `POSTGRES_HOST` | Для prod/ci | `localhost` (хост) / `db` (Docker) | Хост PostgreSQL. Для тестов и `runserver` на хосте — `localhost`. Docker Compose переопределяет на `db` для web/worker. |
| `POSTGRES_PORT` | Нет | `5432` | Порт PostgreSQL. |
| `REDIS_URL` | Для prod | `redis://localhost:6379/0` | Backend кеша аналитики. Без него — fallback на LocMemCache (не для прода) |
| `CELERY_BROKER_URL` | Нет | `redis://localhost:6379/1` | Брокер Celery. Отдельная БД Redis от кеша, чтобы `cache.clear()` не уничтожал очередь. |
| `CELERY_RESULT_BACKEND` | Нет | `redis://localhost:6379/2` | Хранилище результатов задач Celery. |
| `EMAIL_BACKEND` | Нет | `console` | Backend отправки писем. В CI — `locmem`. |
| `DEFAULT_FROM_EMAIL` | Нет | `Hop & Barley <noreply@hopandbarley.com>` | Адрес отправителя. |

---

## Реализованная бизнес-логика

### Каталог товаров (`products`)

- Иерархия категорий через `Category.parent` (self-FK).
- **Фильтр по категории включает дочерние**: клик по «Хмель» показывает товары из «Ароматический хмель» и «Горький хмель».
- Полнотекстовый поиск по имени и описанию (`?q=`, `icontains`).
- Диапазонная фильтрация цен и категорий.
- Сортировка: `newest`, `price_asc`, `price_desc`, `popular`, `name`. Белый список `SORT_MAPPING` защищает от SQL-инъекций через `?sort=`.
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
  2. `filter(stock__gte=qty).update(F(...))` — атомарный SQL-запрос, который работает даже на SQLite.

- **Snapshot цены** в `OrderItem.price`.
- **Email-уведомления вынесены в Celery** — чекаут не блокируется на SMTP.
- **Задачи ставятся в очередь через `transaction.on_commit`** — воркер видит заказ только после коммита.

### Отзывы и рейтинги (`reviews`)

- **Двухфакторная проверка**: оставить отзыв (1–5 звёзд) может только авторизованный клиент, ранее купивший и оплативший (`PAID`) или получивший (`DELIVERED`) товар.
- `UniqueConstraint(fields=['product', 'user'])` на уровне БД — повторный отзыв невозможен.
- **DRY-подход**: бизнес-правило вынесено в `reviews/services.py:get_review_permissions()` и **переиспользуется** в web-view и API-сериализаторе.

### Сервис эмуляции платежей (`payments`)

- Изолированный `PaymentService`:
  - проверяет принадлежность заказа клиенту через `select_for_update().get(id=..., user=user)` — закрывает IDOR архитектурно;
  - валидирует статус (`Pending` → `Paid`);
  - ведёт журнал транзакций с UUID-PK.

- **Трёхуровневая защита от двойной оплаты**:
  1. Проверка статуса в `get_payable_order`.
  2. Проверка статуса под `select_for_update` в `process_payment`.
  3. `UniqueConstraint(fields=['order'], condition=Q(status='SUCCESS'))` на уровне БД.

### Фоновые задачи (`orders.tasks`)

- `send_order_confirmation(order_id)` — письмо покупателю, до 3 повторов с интервалом 60 сек.
- `notify_admins_new_order(order_id)` — уведомление администраторам, до 2 повторов с интервалом 120 сек.
- `fail_silently=False` в `send_mail` — исключение всплывает → Celery делает retry.
- Обе задачи используют `bind=True` и `raise self.retry(exc=exc) from exc` для читаемого traceback.

### Пользователи и безопасность (`users`)

- **Кастомный бэкенд** `EmailOrUsernameModelBackend`: вход по `username` или `email`.
- **Валидация пароля** через `validate_password` — все `AUTH_PASSWORD_VALIDATORS` работают.
- **Нормализация телефона** через `users/phone.py`: любая форма ввода → `+7XXXXXXXXXX` в БД.
- **Экранирование email** через `format_html` вместо `mark_safe` (защита от XSS).
- **Soft Delete** + **реактивация через сброс пароля**.

---

## Спецификация REST API

Базовый путь: `/api/`. Полная документация — в Swagger UI (`/api/docs/`).

| Метод | URL | Права доступа | Назначение |
|-------|-----|---------------|------------|
| POST | `/api/users/register/` | Любой | Регистрация нового покупателя |
| POST | `/api/users/login/` | Любой | Получение JWT-пары (access + refresh) |
| POST | `/api/token/refresh/` | Refresh Token | Ротация access-токена |
| GET | `/api/products/` | Любой | Каталог с пагинацией, фильтрами, поиском |
| GET | `/api/products/{id}/` | Любой | Детальная карточка товара |
| GET | `/api/products/{id}/reviews/` | Любой | Список отзывов товара |
| POST | `/api/products/{id}/reviews/` | Bearer JWT | Добавление отзыва (проверка покупки) |
| GET | `/api/cart/` | Session / JWT | Просмотр корзины |
| POST | `/api/cart/` | Session / JWT | Добавление позиции |
| PATCH | `/api/cart/` | Session / JWT | Изменение количества |
| DELETE | `/api/cart/` | Session / JWT | Очистка корзины |
| POST | `/api/orders/` | Bearer JWT | Создание заказа (атомарное списание остатков, email в Celery) |
| GET | `/api/orders/` | Bearer JWT | Список заказов пользователя |
| GET | `/api/orders/{id}/` | Bearer JWT | Детали своего заказа |
| DELETE | `/api/orders/{id}/` | Bearer JWT | Отмена заказа (возврат остатков) |

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

Ответ `201 Created` приходит мгновенно. Email-уведомления отправляются **асинхронно** Celery-воркером — в логах воркера увидите:

```
[tasks] orders.tasks.send_order_confirmation[abc-123]: succeeded
[tasks] orders.tasks.notify_admins_new_order[def-456]: succeeded
```

### 6. Обновление access-токена

```bash
curl -X POST http://localhost:8080/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

---

## GraphQL API

Эндпоинт `/graphql/` реализован на **Strawberry GraphQL** — type-safe альтернативе Graphene с нативной интеграцией с Django ORM через `strawberry-graphql-django`. Раздел 3.9 ТЗ (бонус).

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
- `config/graphql/context.py` — `GraphQLContext` (доступ к `request.user` и per-request кешу) + кастомный `HopBarleyGraphQLView`.
- `config/graphql/middleware.py` — `GraphQLJWTAuthMiddleware`, читает JWT из заголовка `Authorization: Bearer ...`.
- `config/graphql/permissions.py` — декоратор `@staff_only`, бросает `GraphQLError` с `extensions.code`.
- `config/graphql/cache.py` — декоратор `@cache_metric`, кеширует результаты тяжёлых аналитических резолверов.
- `<app>/graphql/types.py` — GraphQL-типы, привязанные к Django-моделям через `@strawberry_django.type`.
- `<app>/graphql/analytics.py` — резолверы аналитических запросов.

### Аутентификация

Используется **тот же JWT** от `rest_framework_simplejwt`, что и для REST API. После логина через `/api/users/login/` клиент передаёт токен в заголовке:

```
Authorization: Bearer <access_token>
```

`GraphQLJWTAuthMiddleware` перехватывает запросы к `/graphql/`, проверяет подпись и срок действия, и подставляет `request.user`. Если токен отсутствует или невалиден — пользователь остаётся `AnonymousUser`.

### Права доступа

| Резолвер | Гость | Обычный юзер | Staff |
|----------|:-----:|:------------:|:-----:|
| `health` | ✅ | ✅ | ✅ |
| `me` | `null` | ✅ | ✅ |
| `orderMetrics`, `orderTrends` | ❌ UNAUTHENTICATED | ❌ FORBIDDEN | ✅ |
| `popularProducts`, `lowStockProducts`, `outOfStockProducts` | ❌ | ❌ | ✅ |
| `userActivity`, `repeatPurchaseTrend`, `customerLifetimeValue` | ❌ | ❌ | ✅ |

Проверка прав выполняется в декораторе `@staff_only` — **до** тела резолвера, поэтому неавторизованные запросы не нагружают БД.

### Примеры запросов

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

- **Все агрегаты считаются на стороне БД** — `Sum`, `Count`, `Avg`, `Trunc`, `TruncDate/Week/Month`.
- **`DjangoOptimizerExtension`** автоматически применяет `select_related` / `prefetch_related`.
- **Индексы под аналитику** — составные индексы по `(status, paid_at)` и `(user, created_at)`.
- **Кеширование метрик** через `@cache_metric` с per-resolver TTL:
  - `out_of_stock_products` — 60 сек (критично для UX),
  - `low_stock_products` — 120 сек,
  - `order_metrics`, `order_trends`, `user_activity`, `customer_lifetime_value` — 300 сек,
  - `popular_products`, `repeat_purchase_trend` — 600 сек.

### Кеширование

Кеширование аналитических метрик реализовано в `config/graphql/cache.py` через декоратор `@cache_metric`. Порядок декораторов строго:

```python
@strawberry.field
@staff_only              # проверка прав — ДО кеша
@cache_metric(...)       # кеш — только после успешной проверки
def resolver(...): ...
```

Если поменять местами — обычный пользователь получит данные из кеша в обход `@staff_only`. Это **дыра в безопасности**, покрыта регрессионным тестом `test_permissions_checked_before_cache`.

**Backend кеша** — Redis (`django.core.cache.backends.redis.RedisCache`) в проде. В dev и test — fallback на `LocMemCache`, если `REDIS_URL` не задан. В `config/settings/prod.py` — fail-fast: без `REDIS_URL` приложение не стартует, чтобы не работать «вроде бы, но кеш в каждом воркере свой».

**Инвалидация.** Сейчас её нет — метрики «догоняют» данные через TTL. Если понадобится мгновенная актуальность — сбрасывайте кеш через `cache.clear()` или сигналы `post_save` на `Order`.

**Проверка Redis:**

```bash
make flush-cache     # очистить весь кеш
make redis-cli       # зайти в redis-cli
redis-cli KEYS "hopbarley:*"   # посмотреть ключи кеша
```

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

| Параметр | Значение |
|----------|----------|
| `ACCESS_TOKEN_LIFETIME` | 60 минут |
| `REFRESH_TOKEN_LIFETIME` | 7 дней |
| `ROTATE_REFRESH_TOKENS` | `True` |
| `BLACKLIST_AFTER_ROTATION` | `False` |

### GraphQL (аналитика)

- Использует **тот же JWT**, что и REST API — единая точка выпуска токенов.
- Токен передаётся в стандартном заголовке `Authorization: Bearer ...`.
- Эндпоинт `/graphql/` объявлен как `csrf_exempt` — это безопасно, потому что JWT не полагается на cookies, и CSRF-атака технически невозможна.

### Celery (фоновые задачи)

- Email-уведомления не блокируют HTTP-ответ — пользователь получает `201 Created` мгновенно.
- При сбое SMTP задачи ретраятся: до 3 повторов для покупателя, до 2 — для администраторов.
- Задачи попадают в очередь **только после коммита транзакции чекаута** (`transaction.on_commit`).

---

## OpenAPI и интерактивная документация

Схема генерируется `drf-spectacular`:

| Сервис | URL |
|--------|-----|
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| OpenAPI YAML | `/api/schema/` |
| **GraphiQL (GraphQL IDE)** | **`/graphql/`** |

Проверка схемы на валидность:

```bash
poetry run python manage.py spectacular --validate
```

---

## Тестирование и контроль качества

### Запуск тестов

**Через Makefile** — быстро и единообразно:

```bash
make test            # быстрые тесты на SQLite без coverage
make test-all        # полный прогон с coverage
make test-graphql    # только GraphQL
make test-products   # только каталог
make test-orders     # только заказы (включая email)
```

**Вручную** — если нужны нестандартные флаги:

```bash
# Быстро, на SQLite in-memory + LocMemCache
poetry run pytest --ds=config.settings.test

# Как в CI, на PostgreSQL + Redis
poetry run pytest --ds=config.settings.ci --create-db --migrations

# С полным coverage-отчётом
poetry run pytest --ds=config.settings.test --cov=. --cov-report=term-missing --cov-report=html
```

HTML-отчёт: `htmlcov/index.html`.

### Покрытие

Целевой порог — **70%** (`--cov-fail-under=70`).

Декларативные файлы (`apps.py`, `migrations`, `wsgi.py`, `asgi.py`, `urls.py`, `admin.py`, `conftest.py`, `*/graphql/types.py`, `*/graphql/__init__.py`) исключены через `.coveragerc`.

### Структура тестов

- **Модульные тесты приложения** — в `<app>/tests.py`.
- **Сервисные тесты** — в `<app>/tests_services.py`.
- **Интеграционные GraphQL-тесты** — в `tests/graphql/`:
  - `test_permissions.py` — аноним / FORBIDDEN / staff / health.
  - `test_order_analytics.py` — `orderMetrics`, `orderTrends`.
  - `test_product_analitics.py` — `lowStockProducts`, `popularProducts`, `outOfStockProducts`.
  - `test_user_queries.py` — `me`, аналитика пользователей.
  - `test_cache.py` — кеширование метрик и порядок проверки прав относительно кеша.
- **Фикстуры** — в глобальном `conftest.py`. Включают:
  - `staff_user` — staff без superuser.
  - `user_token`, `staff_token`, `admin_token` — JWT для запросов к `/graphql/`.
  - `_clear_cache` (autouse) — сбрасывает кеш до и после каждого теста.

### Тестирование Celery

В `config/settings/test.py` установлено:

```python
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

Это значит, что `.delay()` в тестах выполняется **синхронно**, без воркера. Redis для тестов не нужен.

Тесты email-уведомлений (`orders/tests.py::OrderEmailNotificationTestCase`) используют `self.captureOnCommitCallbacks(execute=True)` — транзакция в `TestCase` не коммитится, и `transaction.on_commit` без этого не сработал бы.

### Статический анализ

**Через Makefile:**

```bash
make lint      # ruff + mypy без изменений
make format    # автоформатирование
```

**Вручную:**

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .
```

### Управление зависимостями

```bash
poetry add <package>                  # основная зависимость
poetry add --group dev <package>      # dev-зависимость
poetry remove <package>               # удалить
poetry lock                           # обновить lock после ручной правки
poetry show --tree                    # дерево зависимостей
```

---

## CI/CD

GitHub Actions workflow — [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — запускается на push и pull request в ветку `dev_3st_week`.

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

CI использует сервис-контейнер Redis для честной проверки кеша аналитики (см. `services: redis:` в workflow). Celery-задачи в CI выполняются в **eager-режиме** (см. `config/settings/ci.py`) — воркер не поднимается.

**Локальная симуляция CI — через Makefile:**

```bash
make up      # поднять db + redis (идемпотентно)
make ci      # полный прогон всех проверок
```

**Или вручную:**

```bash
docker compose up -d db redis

export DJANGO_SETTINGS_MODULE=config.settings.ci
export DJANGO_SECRET_KEY=ci-secret-key-that-is-long-enough-for-hmac-sha256
export POSTGRES_DB=test_db POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost POSTGRES_PORT=5432
export REDIS_URL=redis://localhost:6379/0
export CELERY_BROKER_URL=redis://localhost:6379/1

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

- **Аналитический дашборд**: выручка по оплаченным заказам (`PAID`, `SHIPPED`, `DELIVERED`), счётчик заказов в обработке, число активных клиентов и товаров.
- **Складской контроль**: список позиций с критическим остатком (< 5 шт.).
- **Кастомные actions** в `OrderAdmin`: `mark_as_paid`, `mark_as_shipped`, `show_revenue`.
- **Массовые действия** в `ProductAdmin`: `make_active`, `make_inactive`.
- **Финансовые транзакции read-only**: `PaymentTransactionAdmin` запрещает создание и редактирование.

Аналогичные метрики доступны через GraphQL-эндпоинт `/graphql/` — для интеграции с внешними дашбордами (Grafana, Metabase, BI-системы).

---

## Pre-commit hooks

Проект использует `pre-commit` для автоматической проверки кода **до коммита и push**. Это ловит мелочи (trailing whitespace, order импортов, форматирование) без итерации с CI.

### Установка

```bash
make install                # устанавливает pre-commit + pre-push хуки
```

Или вручную:

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push
```

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

### Если хук поправил файлы

`ruff --fix`, `ruff-format` и `end-of-file-fixer` могут **изменить файлы**. Тогда git прервёт коммит. Это нормально:

```bash
git add .
git commit -m "..."
```

На второй попытке хуки пройдут без правок.

---

## Makefile

Проект использует **Makefile** со шорткатами для типовых команд. Все команды — тонкие обёртки над `poetry` и `docker compose`. Полный список:

```bash
make help
```

### Основные команды

| Команда | Что делает |
|---------|-----------|
| `make install` | Установить зависимости + pre-commit hooks |
| `make run` | Запустить dev-сервер |
| `make worker` | Запустить Celery worker |
| `make beat` | Запустить Celery beat (если появится расписание) |
| `make flower` | Запустить Flower — веб-UI для мониторинга Celery |
| `make shell` | Открыть Django shell |
| `make migrate` / `make makemigrations` | Миграции |
| `make test` | Быстрые тесты на SQLite без coverage |
| `make test-all` | Полный прогон с coverage |
| `make test-graphql` | Только тесты GraphQL |
| `make test-products` | Только тесты каталога |
| `make test-orders` | Только тесты заказов (включая email) |
| `make lint` | `ruff check` + `ruff format --check` + `mypy` |
| `make format` | Автоформатирование и автофиксы |
| `make ci` | Полная симуляция CI перед push |
| `make up` | PostgreSQL (системный или Docker через `pg_isready`) |
| `make up-redis` | Redis в Docker (если системного нет) |
| `make up-all` | Весь стек (db + redis + worker + web) в контейнерах |
| `make down` | Остановить все контейнеры |
| `make logs` | Логи web-контейнера |
| `make logs-worker` | Логи Celery-воркера |
| `make redis-cli` | Зайти в `redis-cli` |
| `make psql` | Зайти в `psql` контейнера БД |
| `make flush-cache` | Очистить весь кеш |
| `make check` | Django system check |
| `make clean` | Удалить артефакты (pycache, htmlcov, .pytest_cache) |

### `make up` идемпотентен

`make up` проверяет через `pg_isready -h localhost -p 5432`, работает ли системный PostgreSQL. Если да — ничего не делает. Если нет — поднимает Docker-контейнер. То же для `make up-redis` (`redis-cli ping`).

Это страхует от падений с `address already in use` на машинах, где уже работают системные сервисы.

### Типичный день

**Терминал 1 — Django:**

```bash
make up              # поднять инфраструктуру
make migrate         # применить миграции
make run             # запустить сервер
```

**Терминал 2 — Celery worker:**

```bash
make worker          # фоновые задачи
```

**После правок кода:**

```bash
make test            # прогнать тесты
make format          # автоформатирование
make ci              # полная проверка перед push
git add . && git commit -m "..." && git push
```

---

## Ограничения и известные компромиссы

### Совместимость с БД

- **`select_for_update()` не работает на SQLite.** Django молча игнорирует этот метод. Защита от overselling работает за счёт `filter(stock__gte=qty).update(F('stock') - qty)`, атомарного на любой БД.
- **Разная семантика `NULL`** в сортировках: SQLite и PostgreSQL по-разному упорядочивают `NULL` при `ORDER BY DESC`.
- **Регистронезависимый поиск** через `icontains` на SQLite не учитывает регистр кириллицы. На PostgreSQL работает корректно.

### Асинхронность и фоновые задачи

- **Email-уведомления вынесены в Celery** (`orders/tasks.py`) — чекаут не блокируется на SMTP.
- **Задачи ставятся в очередь только после коммита** транзакции (`transaction.on_commit`) — воркер не увидит «полу-созданный» заказ.
- **Retry при сбое SMTP**: `send_order_confirmation` — до 3 повторов с интервалом 60 сек, `notify_admins_new_order` — до 2 повторов с интервалом 120 сек.
- **Нет периодических задач** — Celery Beat не настроен, расписания нет.
- **Flower не подключён** — мониторинг задач только через логи воркера.

### GraphQL

- Раздел 3.9 ТЗ (бонус) **реализован** на Strawberry GraphQL.
- Аналитические резолверы защищены `@staff_only`.
- **Кеширование аналитических метрик** реализовано через `@cache_metric`. Backend — Redis в проде, fallback на LocMemCache в dev и test.
- **TTL для метрик разный**: `out_of_stock` — 60 сек, `low_stock` — 120 сек, `popular_products` и `repeat_purchase_trend` — 600 сек, остальные — 300 сек.
- **Инвалидации по сигналам нет** — метрики «догоняют» данные через TTL.
- **Подписки (subscriptions) не реализованы** — требуют Django Channels.
- **Мутации для CRUD в GraphQL отсутствуют** — весь CRUD закрыт через REST API.

### Хранение файлов

- Изображения товаров и аватары хранятся в `FileSystemStorage` (локально).
- Для продакшена рекомендуется S3-совместимое хранилище (`django-storages`).

### Безопасность

- `SECRET_KEY` в Docker Compose берётся из `.env` — для продакшена нужен секрет-менеджер.
- `BLACKLIST_AFTER_ROTATION = False` — украденный refresh-токен можно использовать параллельно с новым.
- `SECURE_HSTS_*`, `SECURE_PROXY_SSL_HEADER` не заданы — при деплое за nginx их надо добавить в `prod.py`.

### Платежи

- **Платёжный шлюз эмурован** (`simulate_success=True`). Реальной интеграции со Stripe/YooKassa/CloudPayments нет.

### Тесты

- Покрытие тестами сфокусировано на бизнес-логике и моделях.
- GraphQL-тесты покрывают права доступа, ключевые метрики и кеш.
- Тесты email-уведомлений работают через `captureOnCommitCallbacks` и eager-режим Celery.
- Нет тестов на race condition (`select_for_update`) — сложно воспроизвести в `TestCase`.

### Инфраструктура

- `docker-compose.yaml` собран для учебного запуска. Для продакшена нужен `gunicorn` вместо `runserver` (закомментирован в compose) и S3 для медиа.
- Медиа-файлы в Docker не сохраняются между перезапусками (volume не настроен).

---

## Лицензия

Учебный проект. Свободно используйте код для обучения и портфолио.

---

**Сделано с ❤️ для сообщества домашних пивоваров.**
