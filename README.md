# Hop & Barley — интернет-магазин товаров для крафтового пивоварения

Полнофункциональный веб-сервис на Django 6.1 и Django REST Framework для онлайн-продажи сырья, ингредиентов, рецептурных наборов и оборудования для домашнего пивоварения.

Архитектура построена по принципу разделения ответственности («тонкие контроллеры, толстый слой сервисов/сериализаторов»). Использует:

- **атомарное списание остатков** через `F()`-выражения и `filter(stock__gte=qty).update(...)` — защита от overselling даже там, где `select_for_update()` не работает;
- **гибридную сессионную корзину** — работает для анонимных и авторизованных пользователей;
- **JWT-аутентификацию** через `djangorestframework-simplejwt`;
- **двухуровневую защиту от двойной оплаты** — `select_for_update` + `UniqueConstraint` на БД;
- **нормализацию телефонов** через `users/phone.py` — единый формат `+7XXXXXXXXXX` в БД;
- **DRY бизнес-правило отзывов** — «только после покупки» живёт в `reviews/services.py` и переиспользуется в web и API;
- **кастомную аналитическую панель** с дашбордом, складским контролем и журналом заказов.

[![CI](https://github.com/VL-code13/hop/actions/workflows/ci.yml/badge.svg?branch=dev_3st_week)](https://github.com/VL-code13/hop/actions/workflows/ci.yml)

## Содержание

- [Технологический стек](#технологический-стек)
- [Архитектурная структура проекта](#архитектурная-структура-проекта)
- [Быстрый старт](#быстрый-старт)
- [Переменные окружения (.env)](#переменные-окружения-env)
- [Реализованная бизнес-логика](#реализованная-бизнес-логика)
- [Спецификация REST API](#спецификация-rest-api)
- [Примеры запросов с JWT](#примеры-запросов-с-jwt)
- [Аутентификация и безопасность](#аутентификация-и-безопасность)
- [OpenAPI и интерактивная документация](#openapi-и-интерактивная-документация)
- [Тестирование и контроль качества](#тестирование-и-контроль-качества)
- [CI/CD](#cicd)
- [Панель администратора и аналитика](#панель-администратора-и-аналитика)
- [Ограничения и известные компромиссы](#ограничения-и-известные-компромиссы)

---

## Технологический стек

| Категория | Технология / Библиотека | Назначение |
|-----------|------------------------|------------|
| Язык | Python 3.12 | Runtime |
| Бэкенд-платформа | Django 6.1.1 | Веб-ядро, ORM, маршрутизация, шаблонизатор, сигналы |
| REST API | Django REST Framework 3.18 | Сериализация, валидация запросов, ViewSets, permissions |
| JWT-авторизация | djangorestframework-simplejwt 5.5.1 | Выпуск, проверка и ротация Access / Refresh токенов |
| Схема OpenAPI | drf-spectacular 0.30.0 | Генерация OpenAPI 3.0, интерактивных Swagger UI и ReDoc |
| Статические файлы | WhiteNoise 6.12 | Раздача сжатой кэшируемой статики с манифестным хешированием |
| СУБД (Production) | PostgreSQL 16 + psycopg 3.3 | Продакшн-база с поддержкой строгой изоляции транзакций |
| СУБД (Development) | SQLite | Встроенная база для ускоренной локальной разработки |
| Тестирование | pytest 9.1 + pytest-django + pytest-cov | Набор из 50+ тестов с автоматическим замером покрытия |
| Статический анализ | Ruff 0.16 + Mypy 1.13 + django-stubs | Линтинг по PEP 8 и статическая типизация |
| Контейнеризация | Docker + Docker Compose | Изоляция сервисов веб-приложения и сервера БД |

---

## Архитектурная структура проекта

```text
hop-and-barley/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions: ruff, mypy, pytest на PostgreSQL
├── config/                     # Настройки проекта
│   ├── settings/
│   │   ├── base.py             # Базовые параметры, JWT, WhiteNoise, DRF
│   │   ├── development.py      # SQLite, DEBUG=True, локальная разработка
│   │   ├── prod.py             # PostgreSQL, security-настройки, строгий WhiteNoise
│   │   └── ci.py               # PostgreSQL, locmem email, для CI и pytest
│   ├── admin.py                # HopBarleyAdminSite с аналитическим дашбордом
│   ├── urls.py                 # Центральный диспетчер маршрутов UI и API
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
│   └── tests.py                # Аутентификация, JWT, soft delete, phone
├── templates/                  # Шаблоны оформления
├── static/                     # CSS, JS, изображения
├── .coveragerc                 # Правила исключений для coverage
├── .dockerignore
├── .env.example
├── docker-compose.yaml
├── Dockerfile
├── pytest.ini
├── pyproject.toml              # Конфигурация Ruff и Mypy
├── requirements.txt
├── conftest.py                 # Глобальные pytest-фикстуры
├── manage.py
└── README.md
```

---

## Быстрый старт

### Вариант A: Локальная разработка (SQLite, без Docker)

Самый быстрый способ запустить проект.

**1. Клонируйте репозиторий и создайте окружение:**

```bash
git clone https://github.com/VL-code13/hop.git
cd hop
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate         # Windows
```

**2. Установите зависимости:**

```bash
pip install -r requirements.txt
```

**3. Создайте `.env` (опционально — `development.py` подставляет дефолты):**

```dotenv
DJANGO_SECRET_KEY=dev-insecure-key-change-me
DJANGO_DEBUG=True
```

**4. Примените миграции и создайте администратора:**

```bash
python manage.py migrate
python manage.py createsuperuser
```

**5. Запустите сервер:**

```bash
python manage.py runserver
```

Приложение: http://127.0.0.1:8000/

### Вариант B: Docker Compose (PostgreSQL + WhiteNoise)

Полный стек: PostgreSQL 16, Django с WhiteNoise. Публичный порт — **8080**.

**1. Подготовьте `.env`:**

```bash
cp .env.example .env
# Отредактируйте DJANGO_SECRET_KEY, POSTGRES_*
# Для использования PostgreSQL задайте:
#   DJANGO_SETTINGS_MODULE=config.settings.prod
#   POSTGRES_HOST=db
```

**2. Запустите контейнеры:**

```bash
docker compose up --build -d
```

**3. Примените миграции и соберите статику:**

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py collectstatic --noinput
```

**Точки входа:**

| Сервис | URL |
|--------|-----|
| Каталог магазина | http://localhost:8080/ |
| Админ-панель с аналитикой | http://localhost:8080/admin/ |
| Swagger UI | http://localhost:8080/api/docs/ |
| ReDoc | http://localhost:8080/api/redoc/ |

> **Важно:** по умолчанию `docker-compose.yaml` собран для учебного запуска. Если `DJANGO_SETTINGS_MODULE` не задан, `web`-контейнер использует `config.settings.development` (SQLite). Для PostgreSQL задайте `DJANGO_SETTINGS_MODULE=config.settings.prod` в `.env`.

---

## Переменные окружения (.env)

| Переменная | Обязательна | По умолчанию | Назначение |
|------------|:-----------:|--------------|------------|
| `DJANGO_SECRET_KEY` | **Да** | — | Секретный ключ. Без него — `ImproperlyConfigured`. |
| `DJANGO_SETTINGS_MODULE` | Нет | `config.settings.development` | Какой конфиг использовать: `development`, `prod`, `ci`. |
| `DJANGO_DEBUG` | Нет | `True` (dev) / `False` (prod) | В `prod.py` guard: `DEBUG=True` разрешён только с `ALLOW_DEBUG_IN_PROD=1`. |
| `DJANGO_ALLOWED_HOSTS` | Нет | `*` (dev) / `example.com` (prod) | Список доверенных хостов через запятую. |
| `POSTGRES_DB` | Для prod/ci | `hopbarley` / `test_db` | Имя базы. |
| `POSTGRES_USER` | Для prod/ci | `user` / `postgres` | Пользователь БД. |
| `POSTGRES_PASSWORD` | Для prod/ci | `p@ssword123` / `postgres` | Пароль. |
| `POSTGRES_HOST` | Для prod/ci | `db` / `localhost` | Хост PostgreSQL. |
| `POSTGRES_PORT` | Нет | `5432` | Порт PostgreSQL. |
| `EMAIL_BACKEND` | Нет | `console` | Backend отправки писем. В CI — `locmem`. |
| `DEFAULT_FROM_EMAIL` | Нет | `Hop & Barley <noreply@hopandbarley.com>` | Адрес отправителя. |

---

## Реализованная бизнес-логика

### Каталог товаров (`products`)

- Расчёт складской доступности через свойство `in_stock`.
- Полнотекстовый поиск по имени и описанию (`?q=`).
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
      id=p.id, stock__gte=qty,
  ).update(stock=F('stock') - qty, updated_at=timezone.now())
  if not updated:
      raise ValidationError('Остаток изменился. Повторите попытку.')
  ```

  Это даёт защиту на **двух уровнях**:
  1. `select_for_update()` блокирует строки на PostgreSQL.
  2. `filter(stock__gte=qty).update(F(...))` — атомарный SQL-запрос, который работает даже на SQLite (где `select_for_update` — no-op).

- **Snapshot цены** в `OrderItem.price`.
- Email-уведомления покупателю и администраторам с `logger.exception` при сбое SMTP.

### Отзывы и рейтинги (`reviews`)

- **Двухфакторная проверка**: оставить отзыв (1–5 звёзд) может только авторизованный клиент, ранее купивший и оплативший (`PAID`) или получивший (`DELIVERED`) товар.
- `UniqueConstraint(fields=['product', 'user'])` на уровне БД — повторный отзыв невозможен.
- **DRY-подход**: бизнес-правило вынесено в `reviews/services.py:get_review_permissions()` и **переиспользуется** в web-view и API-сериализаторе.
- Web-view использует `serializer.is_valid(raise_exception=True)` и конвертирует DRF-исключения в `messages`:
  - `PermissionDenied` (нет покупки) → `messages.error`;
  - `ValidationError` (дубль, плохой рейтинг) → `messages.warning`.

### Сервис эмуляции платежей (`payments`)

- Изолированный `PaymentService`:
  - проверяет принадлежность заказа клиенту через `select_for_update().get(id=..., user=user)` — закрывает IDOR архитектурно;
  - валидирует статус (`Pending` → `Paid`);
  - ведёт журнал транзакций с UUID-PK.

- **Трёхуровневая защита от двойной оплаты**:
  1. Проверка статуса в `get_payable_order`.
  2. Проверка статуса под `select_for_update` в `process_payment`.
  3. `UniqueConstraint(fields=['order'], condition=Q(status='SUCCESS'))` на уровне БД — partial unique index.

- `IntegrityError` от constraint'а конвертируется в `OrderAlreadyPaidError` — пользователь видит понятную ошибку вместо 500.

### Пользователи и безопасность (`users`)

- **Кастомный бэкенд** `EmailOrUsernameModelBackend`: вход по `username` или `email`.
- **Валидация пароля** через `validate_password` — все `AUTH_PASSWORD_VALIDATORS` работают (раньше пароль `123` регистрировался).
- **Нормализация телефона** через `users/phone.py`: любая форма ввода → `+7XXXXXXXXXX` в БД.
- **Экранирование email** через `format_html` вместо `mark_safe` (защита от XSS).
- **Soft Delete** + **реактивация через сброс пароля**.
- Автосоздание `Profile` через сигнал `post_save`.

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
| POST | `/api/orders/` | Bearer JWT | Создание заказа (атомарное списание остатков) |
| GET | `/api/orders/` | Bearer JWT | Список заказов пользователя |
| GET | `/api/orders/{id}/` | Bearer JWT | Детали своего заказа |
| DELETE | `/api/orders/{id}/` | Bearer JWT | Отмена заказа (возврат остатков) |

---

## Примеры запросов с JWT

Ниже — сценарий «от логина до отмены заказа» через `curl`.

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

> Поле называется `username`, но принимает и email — благодаря `EmailOrUsernameModelBackend`.

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
  "payment_method": "card",
  "total_price": "1100.00",
  "shipping_address": "г. Москва, ул. Пивоваров, д. 10, кв. 5",
  "created_at": "2026-01-15T14:30:00Z",
  "items": [
    {
      "id": 1,
      "product": 1,
      "product_name": "Хмель Citra (100г)",
      "price": "550.00",
      "quantity": 2
    }
  ]
}
```

### 6. Добавление отзыва (только после PAID/DELIVERED)

```bash
curl -X POST http://localhost:8080/api/products/1/reviews/ \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"rating": 5, "comment": "Отличный хмель, сварил IPA!"}'
```

Если пользователь не покупал — `403 Forbidden`:

```json
{"detail": "Оставить отзыв можно только на товар, который вы приобрели и оплатили."}
```

### 7. Отмена заказа

```bash
curl -X DELETE http://localhost:8080/api/orders/42/ \
  -H "Authorization: Bearer $ACCESS"
```

Ответ `204 No Content`. Остатки товаров возвращаются на склад атомарно.

### 8. Обновление access-токена

```bash
curl -X POST http://localhost:8080/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

### 9. Ошибка авторизации (без токена)

```bash
curl -X GET http://localhost:8080/api/orders/
```

Ответ `401 Unauthorized`:

```json
{"detail": "Authentication credentials were not provided."}
```

---

## Аутентификация и безопасность

Приложение поддерживает **гибридный режим** контроля доступа.

### Web UI (браузер)

- Сессионная аутентификация Django (`SessionAuthentication`).
- CSRF-токены во всех формах POST.
- `SESSION_COOKIE_AGE = 30 дней`.
- Логаут — только через POST.

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

### Валидация паролей

Все `AUTH_PASSWORD_VALIDATORS` активны — вызываются через `validate_password()` в `UserRegisterForm.clean_password1()`:

- `UserAttributeSimilarityValidator`
- `MinimumLengthValidator`
- `CommonPasswordValidator`
- `NumericPasswordValidator`

### Безопасность production (`config.settings.prod`)

- Guard: `DEBUG=True` разрешён только при `ALLOW_DEBUG_IN_PROD=1`.
- `WHITENOISE_MANIFEST_STRICT = True`.
- `SECRET_KEY` обязателен (иначе `ImproperlyConfigured`).

---

## OpenAPI и интерактивная документация

Схема генерируется `drf-spectacular`:

| Сервис | URL |
|--------|-----|
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| OpenAPI YAML | `/api/schema/` |

Проверка схемы на валидность:

```bash
python manage.py spectacular --validate
```

---

## Тестирование и контроль качества

### Запуск тестов

**Сценарий 1 — быстро, на SQLite:**

```bash
DJANGO_SECRET_KEY=dev pytest --ds=config.settings.development -q --no-cov
```

**Сценарий 2 — как в CI, на PostgreSQL:**

```bash
# 1. Поднять PostgreSQL
docker compose up -d db

# 2. Прогнать тесты
DJANGO_SECRET_KEY=ci-secret-key pytest --create-db --migrations
```

**Сценарий 3 — с полным coverage-отчётом:**

```bash
DJANGO_SECRET_KEY=dev pytest --ds=config.settings.development \
  --cov=. --cov-report=term-missing --cov-report=html
```

HTML-отчёт: `htmlcov/index.html`.

### Покрытие

Целевой порог — **70%** (`--cov-fail-under=70`) по разделу 6.3 ТЗ.

Декларативные файлы (`apps.py`, `migrations`, `wsgi.py`, `asgi.py`, `urls.py`, `admin.py`, `conftest.py`) исключены через `.coveragerc`.

### Структура тестов

| Слой | Где | Стиль |
|------|-----|-------|
| Модели и web-views | `<app>/tests.py` | `django.test.TestCase` |
| Сервисы (без HTTP) | `<app>/tests_services.py` | pytest с `@pytest.mark.django_db` |
| Общие фикстуры | `conftest.py` | `@pytest.fixture` |

### Статический анализ

```bash
# Линтер
ruff check .

# Форматирование
ruff format --check .

# Типизация (django-stubs)
DJANGO_SECRET_KEY=dev DJANGO_SETTINGS_MODULE=config.settings.development mypy .
```

---

## CI/CD

GitHub Actions workflow — [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — запускается на push и pull request в ветку `dev_3st_week`.

**Шаги пайплайна:**

1. **Checkout** и **Setup Python 3.12** с кэшем pip.
2. **Install dependencies** — `pip install -r requirements.txt`.
3. **Ruff check** — `ruff check .`.
4. **Ruff format check** — `ruff format --check .`.
5. **Mypy** — статическая типизация.
6. **Django system check** — `python manage.py check`.
7. **Check migrations** — `python manage.py makemigrations --check --dry-run`.
8. **Run migrations** на PostgreSQL 16 (service container).
9. **Pytest** — `pytest --create-db --migrations --cov-fail-under=70`.

**Конфигурация:**

- `DJANGO_SETTINGS_MODULE=config.settings.ci`.
- PostgreSQL 16 как service container с healthcheck.
- `permissions: contents: read` — минимальные права `GITHUB_TOKEN`.
- `concurrency` — отмена параллельных запусков на одной ветке.
- `timeout-minutes: 15` — защита от зависаний.

**Локальная симуляция CI:**

```bash
docker compose up -d db

export DJANGO_SETTINGS_MODULE=config.settings.ci
export DJANGO_SECRET_KEY=ci-secret-key-that-is-long-enough-for-hmac-sha256
export POSTGRES_DB=test_db POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost POSTGRES_PORT=5432

ruff check . && ruff format --check . && mypy . && \
python manage.py check && \
python manage.py makemigrations --check --dry-run && \
python manage.py migrate --noinput && \
pytest --create-db --migrations --cov-fail-under=70
```

---

## Панель администратора и аналитика

Кастомный `HopBarleyAdminSite` доступен по адресу `/admin/` и включает инструменты мониторинга (раздел 3.6 ТЗ):

- **Аналитический дашборд**: выручка по оплаченным заказам (`PAID`, `SHIPPED`, `DELIVERED`), счётчик заказов в обработке, число активных клиентов и товаров.
- **Складской контроль**: список позиций с критическим остатком (< 5 шт.).
- **Журнал недавних заказов** с прямыми ссылками на редактирование.
- **Кастомные actions** в `OrderAdmin`:
  - `mark_as_paid` — перевод в `Paid` только из `Pending`.
  - `mark_as_shipped` — перевод в `Shipped` только из `Paid`.
  - `show_revenue` — выручка по выбранным заказам с разбивкой по статусам.
- **Аннотации**: `Count('items')`, `Count('products')`.
- **Массовые действия** в `ProductAdmin`: `make_active`, `make_inactive`.
- **Финансовые транзакции read-only**: `PaymentTransactionAdmin` запрещает создание и редактирование — статус меняется только через `PaymentService`.

---

## Ограничения и известные компромиссы

Проект создан в учебных целях — некоторые решения **осознанно упрощены**.

### Совместимость с БД

- **`select_for_update()` не работает на SQLite.** Django молча игнорирует этот метод — реальной блокировки строк не происходит. Защита от overselling работает за счёт `filter(stock__gte=qty).update(F('stock') - qty)`, который атомарен на любой БД.
- **Разная семантика `NULL`** в сортировках: SQLite и PostgreSQL по-разному упорядочивают `NULL` при `ORDER BY DESC`. Для сортировки «популярные» (`-avg_rating`) стоит добавить `nulls_last=True` в `order_by()`.
- **Регистронезависимый поиск** через `icontains` на SQLite не учитывает регистр кириллицы. На PostgreSQL работает корректно.

### Асинхронность и фоновые задачи

- **Email-уведомления отправляются синхронно** внутри транзакции чекаута. В продакшене это стоит вынести в Celery.
- **Нет Celery и Redis** — фоновых задач нет.

### GraphQL

- Раздел 3.9 ТЗ (**бонус**) **не реализован**. Аналитика доступна через REST API и административный дашборд.

### Хранение файлов

- Изображения товаров и аватары хранятся в `FileSystemStorage` (локально).
- Для продакшена рекомендуется S3-совместимое хранилище (`django-storages`).

### Безопасность

- `SECRET_KEY` в Docker Compose берётся из `.env` — для продакшена нужен секрет-менеджер (Vault, AWS Secrets Manager).
- `BLACKLIST_AFTER_ROTATION = False` — украденный refresh-токен можно использовать параллельно с новым. Для включения blacklist нужно добавить `rest_framework_simplejwt.token_blacklist` в `INSTALLED_APPS`.
- `SECURE_HSTS_*`, `SECURE_PROXY_SSL_HEADER` не заданы — при деплое за nginx их надо добавить в `prod.py`.
- `SECURE_SSL_REDIRECT=True` в `config.settings.ci` отключён для тестов через `conftest.py` (autouse-фикстура).

### Платежи

- **Платёжный шлюз эмулирован** (`simulate_success=True`). Реальной интеграции со Stripe/YooKassa/CloudPayments нет.
- Нет webhook-эндпоинта для получения асинхронных уведомлений от платёжного провайдера.

### Тесты

- Покрытие тестами сфокусировано на бизнес-логике и моделях. Views, сериализаторы и API-контроллеры покрыты частично.
- Нет тестов на race condition (`select_for_update`) — сложно воспроизвести в `TestCase`.
- Нет нагрузочных/интеграционных тестов.

### Инфраструктура

- `docker-compose.yaml` собран для учебного запуска. По умолчанию `web`-контейнер использует `config.settings.development` (SQLite), если `DJANGO_SETTINGS_MODULE` не переопределён.
- Медиа-файлы в Docker не сохраняются между перезапусками (volume не настроен).

---

## Лицензия

Учебный проект. Свободно используйте код для обучения и портфолио.

---

**Сделано с ❤️ для сообщества домашних пивоваров.**