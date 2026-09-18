# Hop & Barley — интернет-магазин крафтового пивоварения

Веб-приложение на Django / Django REST Framework для продажи ингредиентов и оборудования для домашнего пивоварения. Включает каталог товаров, корзину на сессиях, оформление заказов, отзывы, JWT-авторизацию для API и кастомную админ-панель с аналитикой.

---

## Содержание

- [Технологии](#технологии)
- [Архитектура проекта](#архитектура-проекта)
- [Быстрый старт](#быстрый-старт)
  - [Вариант A: запуск через Docker](#вариант-a-запуск-через-docker)
  - [Вариант B: запуск без Docker](#вариант-b-запуск-без-docker)
- [Переменные окружения](#переменные-окружения)
- [Функциональные блоки](#функциональные-блоки)
- [REST API](#rest-api)
- [Аутентификация](#аутентификация)
- [Документация API](#документация-api)
- [Тестирование](#тестирование)
- [Админ-панель](#админ-панель)

---

## Технологии

| Категория | Технология | Версия |
|---|---|---|
| Фреймворк | Django | 6.1.1 |
| REST API | Django REST Framework | 3.18 |
| JWT-авторизация | djangorestframework-simplejwt | 5.5.1 |
| Фильтрация | django-filter | 26.1 |
| OpenAPI-схема | drf-spectacular | 0.30 |
| База данных (prod) | PostgreSQL + psycopg | 16 / 3.3.5 |
| База данных (dev) | SQLite | встроенная |
| Тестирование | pytest + pytest-django | 9.1 / 4.14 |
| Загрузка переменных | python-dotenv | 1.2.3 |
| Работа с изображениями | Pillow | 12.3 |
| Контейнеризация | Docker + Docker Compose | — |

---

## Архитектура проекта

```
hop-barley/
├── config/                     # Конфигурация проекта
│   ├── settings/
│   │   ├── base.py             # Общие настройки, INSTALLED_APPS, REST_FRAMEWORK, JWT
│   │   ├── development.py      # SQLite, DEBUG=True
│   │   └── prod.py             # PostgreSQL, DEBUG=False
│   ├── urls.py                 # Главные маршруты
│   ├── admin.py                # Кастомный AdminSite с дашбордом
│   ├── wsgi.py
│   └── asgi.py
├── products/                   # Каталог товаров
│   ├── models.py               # Category, Product
│   ├── views.py                # ProductListView, ProductDetailView, GuidesRecipesView
│   ├── api_views.py            # ProductViewSet (DRF)
│   ├── serializers.py          # Сериализаторы товаров и категорий
│   ├── forms.py                # AddToCartProductForm (валидация по остатку)
│   ├── admin.py                # Админка категорий и товаров
│   ├── urls.py
│   └── tests.py
├── orders/                     # Заказы и корзина
│   ├── models.py               # Order, OrderItem
│   ├── cart.py                 # Cart — сессионная корзина
│   ├── views.py                # Cart-контроллеры, OrderCreateView
│   ├── api_views.py            # CartAPIView, OrderViewSet (DRF)
│   ├── serializers.py          # Сериализаторы заказов и корзины
│   ├── forms.py                # OrderCreateForm (контакты, адрес, оплата)
│   ├── context_processors.py  # Корзина в контексте шаблонов
│   ├── admin.py                # Админка заказов с actions
│   ├── urls.py
│   └── tests.py
├── users/                      # Пользователи и аутентификация
│   ├── models.py               # Profile (доп. поля пользователя)
│   ├── views.py                # Регистрация, вход, личный кабинет, смена пароля
│   ├── forms.py                # LoginForm, RegisterForm, ProfileForm, PasswordChangeForm
│   ├── backends.py             # Аутентификация по email или username
│   ├── signals.py              # Автосоздание Profile
│   ├── admin.py
│   ├── urls.py
│   └── tests.py
├── templates/                  # HTML-шаблоны
│   ├── base.html               # Базовый шаблон (хедер, навигация, футер)
│   ├── product_list.html       # Каталог с фильтрами и пагинацией
│   ├── product_detail.html     # Карточка товара + отзывы
│   ├── cart_detail.html        # Корзина
│   ├── checkout.html          # Оформление заказа
│   ├── order_success.html     # Успешный заказ
│   ├── account.html            # Личный кабинет
│   ├── login.html              # Вход
│   ├── register.html           # Регистрация
│   ├── guides-recipes.html     # Гайды и рецепты
│   ├── password_reset_*.html   # Сброс пароля (4 этапа)
│   └── index.html              # Кастомный дашборд админки
├── docker-compose.yaml
├── Dockerfile
├── .env.example
├── requirements.txt
├── manage.py
└── README.md
```

---

## Быстрый старт

### Вариант A: запуск через Docker

> Окружение: PostgreSQL 16 + Django (runserver). Порт приложения — **8080**.

**1. Клонирование репозитория**

```bash
git clone <url-репозитория>
cd hop-barley
```

**2. Настройка переменных окружения**

```bash
cp .env.example .env
```

Откройте `.env` и заполните значения:

```dotenv
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False

POSTGRES_DB=hopbarley
POSTGRES_USER=user
POSTGRES_PASSWORD=p@ssword123
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

> В Docker Compose `POSTGRES_HOST` автоматически устанавливается в `db` — имя сервиса. Менять не нужно.

**3. Сборка и запуск контейнеров**

```bash
docker compose up --build
```

Docker Compose поднимет два сервиса:

| Сервис | Контейнер | Порт | Назначение |
|---|---|---|---|
| `db` | `hop_and_barley_db` | 5432 | PostgreSQL 16 |
| `web` | `hop_and_barley_web` | 8080 → 8000 | Django (runserver) |

**4. Применение миграций и создание суперпользователя**

В отдельном терминале:

```bash
# Миграции
docker compose exec web python manage.py migrate

# Фикстуры (если есть)
docker compose exec web python manage.py loaddata products/fixtures/*.json

# Суперпользователь
docker compose exec web python manage.py createsuperuser

# Сбор статики
docker compose exec web python manage.py collectstatic --noinput
```

**5. Доступ**

| URL | Назначение |
|---|---|
| `http://localhost:8080/` | Каталог товаров |
| `http://localhost:8080/admin/` | Админ-панель |
| `http://localhost:8080/api/` | REST API |
| `http://localhost:8080/api/docs/` | Swagger UI |

**Остановка:**

```bash
docker compose down          # остановить контейнеры
docker compose down -v       # остановить + удалить тома БД
```

---

### Вариант B: запуск без Docker

> Окружение: SQLite, `DEBUG=True`. Подходит для локальной разработки.

**1. Клонирование и виртуальное окружение**

```bash
git clone <url-репозитория>
cd hop-barley

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate          # Windows
```

**2. Установка зависимостей**

```bash
pip install -r requirements.txt
```

**3. Настройка переменных окружения**

```bash
cp .env.example .env
```

Для локальной разработки достаточно указать только ключ:

```dotenv
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
```

> В режиме разработки (`config.settings.development`) используется SQLite, параметры PostgreSQL не требуются.

**4. Миграции и фикстуры**

```bash
python manage.py migrate
python manage.py loaddata products/fixtures/*.json   # если есть фикстуры
```

**5. Создание суперпользователя**

```bash
python manage.py createsuperuser
```

**6. Запуск сервера**

```bash
python manage.py runserver
```

**7. Доступ**

| URL | Назначение |
|---|---|
| `http://localhost:8000/` | Каталог товаров |
| `http://localhost:8000/admin/` | Админ-панель |
| `http://localhost:8000/api/` | REST API |
| `http://localhost:8000/api/docs/` | Swagger UI |

---

## Переменные окружения

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `DJANGO_SECRET_KEY` | Секретный ключ Django | — (обязательно) |
| `DJANGO_DEBUG` | Режим отладки | `False` |
| `POSTGRES_DB` | Имя базы данных PostgreSQL | `hopbarley` |
| `POSTGRES_USER` | Пользователь БД | `user` |
| `POSTGRES_PASSWORD` | Пароль БД | `p@ssword123` |
| `POSTGRES_HOST` | Хост БД (`db` в Docker) | `db` |
| `POSTGRES_PORT` | Порт БД | `5432` |

> В режиме разработки (`development.py`) переменные PostgreSQL игнорируются — используется SQLite.

---

## Функциональные блоки

### Каталог товаров (`/products/`)

- Список товаров с пагинацией (по 6 на страницу)
- Фильтрация по категории и диапазону цен
- Поиск по названию и описанию
- Сортировка: по новизне, по возрастанию / убыванию цены

| Параметр | Тип | Описание |
|---|---|---|
| `category` | slug | Фильтр по категории |
| `min_price` | число | Минимальная цена |
| `max_price` | число | Максимальная цена |
| `q` | строка | Поиск по названию и описанию |
| `sort` | `new` / `price_asc` / `price_desc` | Сортировка |

### Карточка товара (`/product/<slug>/`)

- Детальная информация: название, описание, цена, остаток, дата поступления
- Форма добавления в корзину с валидацией по складскому остатку
- Отзывы пользователей с рейтингом (1–5 звёзд)
- Форма отзыва доступна только авторизованным пользователям

### Корзина (`/cart/`)

- Хранение в сессии Django (`CART_SESSION_ID`)
- Подсчёт стоимости каждой позиции и общей суммы
- Учёт остатка: нельзя добавить больше, чем есть на складе
- Изменение количества и удаление товаров

### Оформление заказа (`/checkout/`)

- Форма контактов: ФИО, телефон (валидация формата РФ), адрес доставки
- Выбор способа оплаты: карта онлайн, электронный кошелёк / СБП, наличные при получении
- Создание заказа со снимком цен на момент оформления
- Списание товара со склада
- Страница успешного оформления с номером заказа

### Личный кабинет (`/account/`)

- История заказов с позициями и статусами
- Редактирование профиля: имя, фамилия, email, телефон, адрес доставки
- Смена пароля
- Выход из аккаунта

### Аутентификация

- Регистрация по email и паролю
- Вход по email **или** имени пользователя (кастомный бэкенд `users.backends.py`)
- Восстановление пароля: форма → письмо со ссылкой → установка нового пароля
- Автосоздание профиля при регистрации (сигнал `post_save`)

---

## REST API

Базовый URL: `/api/`

### Эндпоинты

| Метод | URL | Авторизация | Описание |
|---|---|---|---|
| `POST` | `/api/token/` | — | Получение JWT-пары (access + refresh) |
| `POST` | `/api/token/refresh/` | refresh-токен | Обновление access-токена |
| `GET` | `/api/products/` | — | Список товаров (фильтрация, поиск, сортировка) |
| `GET` | `/api/products/<id>/` | — | Детальная информация о товаре |
| `GET` | `/api/cart/` | — | Содержимое сессионной корзины |
| `POST` | `/api/cart/` | — | Добавление товара в корзину |
| `PATCH` | `/api/cart/<product_id>/` | — | Обновление количества |
| `DELETE` | `/api/cart/<product_id>/` | — | Удаление товара из корзины |
| `GET` | `/api/orders/` | JWT | Список заказов текущего пользователя |
| `POST` | `/api/orders/` | JWT | Создание заказа из сессионной корзины |
| `GET` | `/api/orders/<id>/` | JWT | Детальная информация о заказе |

### Примеры запросов

**Получение JWT-токена:**

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "brewmaster@example.com", "password": "strong_password_123"}'
```

**Создание заказа:**

```bash
curl -X POST http://localhost:8000/api/orders/ \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"shipping_address": "Москва, ул. Хмелевая, 1", "payment_method": "card"}'
```

**Просмотр корзины:**

```bash
curl http://localhost:8000/api/cart/ \
  -H "Cookie: sessionid=<session-id>"
```

---

## Аутентификация

| Свойство | Session (веб) | JWT (API) |
|---|---|---|
| Механизм | Cookies + сессии Django | Access + refresh токены |
| Используется для | Шаблоны, браузерные страницы | REST API, внешние клиенты |
| Вход | `POST /login/` (форма) | `POST /api/token/` |
| Выход | `POST /logout/` | Удаление токена на клиенте |
| Время жизни access | Сессия браузера | 15 минут (настраивается) |
| Время жизни refresh | — | 7 дней (настраивается) |

---

## Документация API

Документация OpenAPI генерируется автоматически через `drf-spectacular`:

| Интерфейс | URL |
|---|---|
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| Схема YAML | `/api/schema/` |

---

## Тестирование

```bash
# Все тесты
pytest

# Тесты конкретного приложения
pytest products/
pytest orders/
pytest users/

# С подробным выводом
pytest -v

# С покрытием (если установлен pytest-cov)
pytest --cov=. --cov-report=term
```

| Приложение | Что покрывает |
|---|---|
| `products` | Каталог, поиск, фильтрация, бизнес-правила остатков |
| `orders` | Корзина, складские лимиты, оформление заказа |
| `users` | Регистрация, вход, профиль, JWT-токены |

---

## Админ-панель

Кастомная админ-панель доступна по `/admin/` и включает:

- **Дашборд** — общая выручка, количество заказов, пользователи, активные товары
- **Управление остатками** — список товаров с ценами, категориями и остатками
- **Добавление / редактирование товара** — форма с изображением
- **Заказы** — фильтры по статусу и способу оплаты, поиск, кастомные действия
- **Пользователи** — список с инлайн-профилями

Создание суперпользователя:

```bash
python manage.py createsuperuser
# или в Docker:
docker compose exec web python manage.py createsuperuser
```
