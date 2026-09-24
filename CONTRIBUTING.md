# Contributing to Hop & Barley

Спасибо за интерес к проекту! Этот документ описывает процесс разработки, стандарты кода и требования к изменениям.

## Содержание

- [Кодекс поведения](#кодекс-поведения)
- [Настройка окружения](#настройка-окружения)
- [Git workflow](#git-workflow)
- [Стандарты кода](#стандарты-кода)
- [Pre-commit hooks](#pre-commit-hooks)
- [Makefile — шорткаты для типовых команд](#makefile--шорткаты-для-типовых-команд)
- [Управление зависимостями (Poetry)](#управление-зависимостями-poetry)
- [Тестирование](#тестирование)
- [Коммиты](#коммиты)
- [Pull Request](#pull-request)
- [Чек-лист перед push](#чек-лист-перед-push)
- [Сообщение об ошибке](#сообщение-об-ошибке)

---

## Кодекс поведения

- Будьте увазительны в комментариях и ревью.
- Критикуйте код, а не автора.
- Задавайте вопросы, если что-то непонятно — лучше уточнить, чем переделать.
- Не публикуйте личные данные (email, телефоны) в issues и PR.

---

## Настройка окружения

### Требования

| Инструмент | Версия |
|------------|--------|
| Python | 3.12+ |
| **Poetry** | **2.0+** |
| PostgreSQL | 16 (для тестов и продакшена) |
| **Redis** | **7+** (кеш аналитических метрик GraphQL) |
| Docker | 24+ (опционально, для БД и Redis) |
| Git | 2.40+ |

**Установка Poetry** (если не установлена):

```bash
pipx install poetry
# или
curl -sSL https://install.python-poetry.org | python3 -
```

### Установка проекта — через Makefile

Все типовые команды обёрнуты в `Makefile`. Полный список — `make help`.

```bash
# 1. Клонировать репозиторий
git clone https://github.com/VL-code13/hop.git
cd hop

# 2. Установить зависимости и pre-commit hooks
make install

# 3. Создать .env из шаблона
cp .env.example .env
# Отредактируйте DJANGO_SECRET_KEY:
poetry run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

# 4. Поднять PostgreSQL и Redis
make up

# 5. Применить миграции
make migrate

# 6. Создать администратора
poetry run python manage.py createsuperuser

# 7. Запустить сервер
make run
```

### Установка проекта — вручную

Если `make` недоступен (например, на Windows без WSL):

```bash
# 1. Клонировать репозиторий
git clone https://github.com/VL-code13/hop.git
cd hop

# 2. Установить зависимости
poetry install

# 3. Установить pre-commit hooks
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push

# 4. Создать .env из шаблона
cp .env.example .env
poetry run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

# 5. Поднять PostgreSQL и Redis
docker compose up -d db redis

# 6. Прописать REDIS_URL в .env (если ещё не прописан)
echo "REDIS_URL=redis://localhost:6379/0" >> .env

# 7. Применить миграции
poetry run python manage.py migrate

# 8. Создать администратора
poetry run python manage.py createsuperuser

# 9. Запустить сервер разработки
poetry run python manage.py runserver
```

### Полезные команды Poetry

```bash
# Активировать виртуальное окружение — дальше можно без префикса `poetry run`
poetry shell

# Выйти из окружения
exit

# Показать информацию об окружении
poetry env info

# Список установленных пакетов
poetry show
poetry show --only main
poetry show --only dev
```

### Docker (опционально, для PostgreSQL и Redis)

```bash
make up              # поднять db + redis
make down            # остановить всё
make logs            # логи web-контейнера

# Или вручную:
docker compose up -d db redis           # только БД и кеш
docker compose up --build -d            # весь стек (db + redis + web)
```

### Проверка Redis

Убедиться, что кеш работает через Redis, а не через fallback `LocMemCache`:

```bash
poetry run python manage.py shell -c "
from django.core.cache import caches
cache = caches['default']
cache.set('ping', 'pong', 10)
print(cache.__class__.__name__, cache.get('ping'))
"
# Ожидаемо: RedisCache pong
```

Если вывело `LocMemCache` — значит `REDIS_URL` не подхватился. Проверь:

```bash
grep REDIS .env            # должно быть REDIS_URL=redis://localhost:6379/0
redis-cli ping             # → PONG
```

---

## Git workflow

### Основные ветки

| Ветка | Назначение |
|-------|------------|
| `main` | Стабильная версия. Только через PR. |
| `dev_3st_week` | Текущая ветка разработки (учебная). |
| `feature/<название>` | Новая функциональность. |
| `bugfix/<название>` | Исправление багов. |
| `hotfix/<название>` | Срочные фиксы на проде. |
| `docs/<название>` | Только документация. |
| `chore/<название>` | Технические изменения (зависимости, CI). |

### Создание ветки под задачу

```bash
git checkout dev_3st_week
git pull origin dev_3st_week
git checkout -b feature/product-reviews
```

### Правила именования веток

- **Только латиница, lowercase, дефисы.**
- Отражает суть задачи: `feature/cart-stock-validation`, а не `feature/my-branch-1`.
- Не используйте пробелы, кириллицу, точки.

---

## Стандарты кода

### Общие требования

- **PEP 8** соблюдается через `ruff`.
- **Типизация** обязательна для публичных функций и методов — через `mypy` и `django-stubs`.
- **Docstrings** — для всех публичных модулей, классов и функций.
- **Комментарии** — только для объяснения «почему», а не «что».

### Линтеры и форматтеры

Через Makefile:

```bash
make lint       # ruff check + ruff format --check + mypy (без изменений)
make format     # автоформатирование и автофиксы
```

Вручную:

```bash
# Проверка
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy .

# Автоисправление
poetry run ruff check . --fix
poetry run ruff format .
```

### Стиль кода

- Кавычки — **одинарные** (`'string'`).
- Длина строки — **120** символов.
- Отступы — **4 пробела** (не табы).
- Импорты сгруппированы: stdlib → third-party → first-party (проверяет `ruff`).

### Пример правильного кода

```python
"""Модуль для работы с корзиной."""

from decimal import Decimal

from django.http import HttpRequest


def calculate_total_price(cart_items: list[dict]) -> Decimal:
    """Считает итоговую стоимость позиций корзины.

    Args:
        cart_items: Список словарей с ключами `price` и `quantity`.

    Returns:
        Decimal: Сумма `price * quantity` по всем позициям.
    """
    return sum(
        (Decimal(str(item['price'])) * item['quantity'] for item in cart_items),
        Decimal('0.00'),
    )
```

### Чего избегать

- `print()` — использовать `logging`.
- Магические числа — выносить в константы (`Final`).
- `except Exception: pass` — как минимум логировать через `logger.exception()`.
- Длинные функции (> 40 строк) — декомпозировать.
- `SELECT N+1` — использовать `select_related` / `prefetch_related`.

### GraphQL-специфика

При работе с GraphQL-слоем (Strawberry) соблюдай дополнительные правила:

- **Forward references в аннотациях** (`'ClassName'`) недопустимы, если класс не определён в этом же модуле. Strawberry не сможет разрешить тип при сборке схемы.
- **Импорты типов — только на уровне модуля.** Не импортируй Strawberry-типы внутри функций — это ломает `get_type_hints()`.
- **Порядок декораторов строго такой:**

  ```python
  @strawberry.field         # внешний
  @staff_only               # проверка прав — ДО кеша
  @cache_metric(...)        # кеш — только после успешной проверки
  def resolver(...): ...
  ```

  Если поменять местами `staff_only` и `cache_metric`, обычный пользователь получит данные из кеша в обход проверки прав. Это **дыра в безопасности**, покрыта регрессионным тестом `test_permissions_checked_before_cache`.
- **Не используй `ModelType.from_django(...)`** — такого метода нет. Возвращай инстанс модели напрямую, Strawberry сам конвертирует его в GraphQL-тип.
- **Таймзоны:** для фильтрации по `__date` используй `timezone.localdate()`, а не `timezone.now().date()`. Иначе фильтр в UTC разойдётся с ORM, который конвертирует в `TIME_ZONE`.
- **Денежные значения квантизуй:** `.quantize(Decimal('0.01'))` — иначе `str(Decimal('1000'))` вернёт `'1000'` вместо `'1000.00'`.
- **Docstrings** — на каждый резолвер, с описанием аргументов и прав доступа.

### PEP 695 — параметризованные функции

Проект использует Python 3.12, поэтому Ruff включает правило `UP047` — требование PEP 695 синтаксиса для generic-функций. Вместо:

```python
from typing import TypeVar
F = TypeVar('F', bound=Callable[..., Any])

def decorator(func: F) -> F: ...
```

пиши:

```python
def decorator[F: Callable[..., Any]](func: F) -> F: ...
```

Параметры типа объявляются прямо в сигнатуре функции — до `(...)`.

### Кеширование

Аналитические метрики GraphQL кешируются через `@cache_metric` (см. `config/graphql/cache.py`). При работе с кешем помни:

- **Backend абстрагирован.** Декоратор работает через `django.core.cache`, конкретный backend (Redis или LocMemCache) выбирается в настройках. Резолверы об этом не знают.
- **`REDIS_URL` — единственная точка конфигурации.** Задан → `RedisCache`. Не задан → fallback на `LocMemCache` (только для dev и тестов).
- **В тестах — всегда `LocMemCache`.** `config/settings/test.py` переопределяет `CACHES`, чтобы тесты не зависели от Redis.
- **Порядок декораторов — вопрос безопасности.** См. «GraphQL-специфика» выше.

Если добавляешь новый кешируемый резолвер, оборачивай так:

```python
@strawberry.field
@staff_only
@cache_metric(ttl=300, prefix='<домен>')
def resolver(...): ...
```

TTL выбирай по частоте изменений данных: 60 сек для «горячих» метрик (`out_of_stock`), 600 сек для медленных (`popular_products`).

---

## Pre-commit hooks

Проект использует `pre-commit` для автоматического запуска линтеров, форматтеров и тестов **до коммита и push**. Это страхует от мелочей, на которых обычно падает CI: пробелы, порядок импортов, забытые тесты.

### Установка

Устанавливается автоматически через `make install`. Или вручную:

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push
```

Первая команда — `pre-commit` хук (запускается на `git commit`).
Вторая — `pre-push` хук (запускается на `git push`, гоняет mypy и pytest).

Один раз на клонирование. Дальше работает автоматически.

### Что запускается

**На `git commit`** — быстрые хуки:

- `trailing-whitespace`, `end-of-file-fixer`, `mixed-line-ending` — чистка файлов;
- `check-yaml`, `check-toml` — синтаксис конфигов;
- `check-added-large-files`, `check-merge-conflict`, `detect-private-key` — защита;
- `ruff --fix` — линтер с автоисправлениями;
- `ruff-format` — форматтер.

**На `git push`** — тяжёлые проверки:

- `mypy .` — статическая типизация;
- `pytest --ds=config.settings.test --no-cov -q` — быстрые тесты.

### Ручной запуск

```bash
# Прогнать хуки на staged-файлах (как при коммите)
poetry run pre-commit run

# Прогнать на всех файлах проекта
poetry run pre-commit run --all-files
```

### Если хук поправил файлы

`ruff --fix`, `ruff-format`, `end-of-file-fixer` и `trailing-whitespace` **изменяют файлы**. Git прервёт коммит. Это нормально:

```bash
git add .                        # добавить изменения от хуков
git commit -m "..."              # повторить
```

На второй попытке хуки пройдут без правок.

### Пропустить проверку (экстренно)

```bash
# Пропустить pre-commit для одного коммита
git commit --no-verify -m "..."

# Пропустить pre-push
git push --no-verify
```

**Не используй без необходимости.** Если CI обязателен — пропуск локальных хуков не поможет, просто найдёшь проблему позже.

### Обновление версий хуков

Раз в пару месяцев:

```bash
poetry run pre-commit autoupdate
```

Обновит `rev:` во всех репозиториях до последних версий. Затем:

```bash
git add .pre-commit-config.yaml
git commit -m "chore(ci): обновить pre-commit hooks"
```

---

## Makefile — шорткаты для типовых команд

Проект использует `Makefile` со шорткатами для типовых команд. Все цели — тонкие обёртки над `poetry` и `docker compose`.

### Получить список команд

```bash
make help
```

### Основные команды

| Команда | Что делает |
|---------|-----------|
| `make install` | Установить зависимости + pre-commit hooks |
| `make run` | Запустить dev-сервер |
| `make shell` | Открыть Django shell |
| `make migrate` / `make makemigrations` | Миграции |
| `make test` | Быстрые тесты на SQLite без coverage |
| `make test-all` | Полный прогон с coverage |
| `make test-graphql` | Только тесты GraphQL |
| `make test-products` | Только тесты каталога |
| `make lint` | `ruff check` + `ruff format --check` + `mypy` |
| `make format` | Автоформатирование и автофиксы |
| `make ci` | Полная симуляция CI перед push |
| `make up` / `make down` | Поднять/остановить db + redis |
| `make logs` | Логи web-контейнера |
| `make redis-cli` | Зайти в `redis-cli` |
| `make psql` | Зайти в `psql` контейнера БД |
| `make flush-cache` | Очистить весь кеш |
| `make check` | Django system check |
| `make clean` | Удалить артефакты (pycache, htmlcov, .pytest_cache) |

### Типичный день

```bash
make up              # поднять инфраструктуру
make migrate         # применить миграции
make run             # запустить сервер

# ... код ...

make test            # прогнать тесты
make format          # автоформатирование
make ci              # полная проверка перед push
git add . && git commit -m "..." && git push
```

### Если `make` недоступен

На Windows без WSL — используй команды напрямую (см. разделы ниже). Все `make`-цели — обёртки над `poetry run ...` и `docker compose ...`, ничего магического.

---

## Управление зависимостями (Poetry)

Проект использует **Poetry 2.x** с PEP 621 манифестом (`[project]`) и PEP 735 группами (`[dependency-groups]`).

### Структура `pyproject.toml`

```toml
[project]
name = "hop-and-barley"
...
dependencies = [
    "django==6.1.1",
    "strawberry-graphql (>=0.327.7,<0.328.0)",
    "strawberry-graphql-django (>=0.89.2,<0.90.0)",
    "redis==6.4.0",
    ...
]

[dependency-groups]
dev = [
    "pytest==9.1.1",
    "pre-commit==4.0.1",
    ...
]

[tool.poetry]
package-mode = false    # это приложение, а не публикуемый пакет
```

### Добавление зависимостей

```bash
# Основная зависимость (пойдёт в прод)
poetry add <package>
poetry add "django-filter@^26.0"        # с ограничением версии
poetry add "psycopg[binary]==3.3.5"     # с extras

# Dev-зависимость (тесты, линтеры, стабы)
poetry add --group dev <package>
poetry add --group dev pytest-mock
```

### Удаление зависимостей

```bash
poetry remove <package>
poetry remove --group dev <package>
```

### Обновление

```bash
# Обновить все пакеты в рамках ограничений из pyproject.toml
poetry update

# Обновить один пакет
poetry update django

# Пересобрать lock-файл после ручной правки pyproject.toml
poetry lock
```

### Просмотр зависимостей

```bash
poetry show                  # все установленные
poetry show --only main      # только продакшен
poetry show --only dev       # только dev
poetry show --tree           # дерево зависимостей
poetry show <package>        # информация о пакете
```

### Ручное редактирование `pyproject.toml`

Если правите `dependencies` или `[dependency-groups]` вручную — **обязательно** пересоберите lock:

```bash
poetry lock
```

Иначе `poetry install` упадёт с рассинхроном между манифестом и lock-файлом.

### Что коммитить

| Файл | Коммитить? |
|------|:----------:|
| `pyproject.toml` | ✅ Да |
| `poetry.lock` | ✅ **Да** (обязательно) |
| `.venv/` | ❌ Нет (в `.gitignore`) |
| `requirements.txt` | ❌ Нет (устаревший формат) |

**`poetry.lock` коммитится всегда** — это стандарт Poetry. Без него у разных разработчиков будут разные версии пакетов, и CI станет невоспроизводимым.

---

## Тестирование

### Минимальные требования к PR

- Новый функционал **обязан** иметь тесты.
- Багфиксы сопровождаются **регрессионным тестом**.
- Покрытие не должно падать (`--cov-fail-under=70`).

### Запуск тестов

Через Makefile:

```bash
make test            # быстрые тесты на SQLite in-memory
make test-all        # полный прогон с coverage
make test-graphql    # только GraphQL
make test-products   # только каталог
```

Вручную:

```bash
# Быстро, на SQLite in-memory + LocMemCache
poetry run pytest --ds=config.settings.test

# Как в CI, на PostgreSQL + Redis
docker compose up -d db redis
poetry run pytest --ds=config.settings.ci --create-db --migrations

# С покрытием
poetry run pytest --ds=config.settings.test --cov=. --cov-report=html
```

### Проверка Redis-интеграции

Локальные тесты идут на `LocMemCache` (см. `config/settings/test.py`), поэтому **явную проверку Redis-интеграции** можно сделать отдельно:

```bash
poetry run python manage.py shell -c "
from django.core.cache import caches
print(caches['default'].__class__.__name__)
"
# Ожидаем: RedisCache (если REDIS_URL задан и Redis запущен)
```

Для интеграционного теста — `tests/integration/test_redis_cache.py` (если добавлен в проект). Он помечен `pytest.mark.skipif` и запускается только при наличии `REDIS_URL`.

### Структура тестов

- **Модульные тесты** — в `<app>/tests.py`.
- **Сервисные тесты** — в `<app>/tests_services.py` (без HTTP-клиента).
- **Интеграционные GraphQL-тесты** — в `tests/graphql/`:
  - `test_permissions.py` — права доступа (`UNAUTHENTICATED` / `FORBIDDEN` / staff).
  - `test_order_analytics.py` — `orderMetrics`, `orderTrends`.
  - `test_product_analitics.py` — `lowStockProducts`, `popularProducts`, `outOfStockProducts`.
  - `test_user_queries.py` — `me`, аналитика пользователей.
  - `test_cache.py` — кеширование метрик и порядок проверки прав относительно кеша.
- **Фикстуры** — в глобальном `conftest.py`. В том числе:
  - `staff_user` — staff без superuser (для проверки аналитики).
  - `user_token`, `staff_token`, `admin_token` — JWT для запросов к `/graphql/`.
  - `_clear_cache` (autouse) — сбрасывает кеш до и после каждого теста. Без неё кеш живёт между тестами и ломает изоляцию: тест, прогревающий аналитический резолвер, «протечёт» в следующий тест и вернёт устаревшие данные.

### Тестирование GraphQL с JWT

Пример теста с авторизацией:

```python
@pytest.mark.django_db
def test_analytics_available_for_staff(staff_token: str) -> None:
    """Staff-пользователь получает данные аналитики."""
    response = Client().post(
        '/graphql/',
        data='{"query": "{ orderMetrics { orderCount } }"}',
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {staff_token}',
    )
    payload = response.json()
    assert 'errors' not in payload
    assert payload['data']['orderMetrics']['orderCount'] == 0
```

**Важно:** GraphQL может вернуть `data: null` целиком (а не `data.orderMetrics: null`), когда упавший резолвер помечен как non-nullable. Поэтому в тестах проверяй `payload.get('data') is None or payload['data'].get('orderMetrics') is None` — это безопаснее.

### Тестирование кеша

Декоратор `@cache_metric` кеширует результат резолвера в `django.core.cache`. В тестах важно помнить:

- **Кеш не сбрасывается между тестами автоматически.** Autouse-фикстура `_clear_cache` в `conftest.py` решает это.
- **Проверка прав должна идти до кеша.** Это покрыто тестом `test_permissions_checked_before_cache` — если кто-то поменяет порядок декораторов, тест упадёт.
- **Тесты работают на `LocMemCache`.** В `config/settings/test.py` `CACHES` жёстко указывает на `LocMemCache`, чтобы не зависеть от поднятого Redis. Если хочешь проверить именно Redis — отдельный тест с `pytest.mark.skipif`.

---

## Коммиты

### Формат сообщения

Соблюдаем [Conventional Commits](https://www.conventionalcommits.org/):

```
<тип>(<область>): <краткое описание>
```

### Типы коммитов

| Тип | Когда использовать |
|-----|-------------------|
| `feat` | Новая функциональность |
| `fix` | Исправление бага |
| `refactor` | Рефакторинг без изменения поведения |
| `test` | Добавление/правка тестов |
| `docs` | Только документация |
| `style` | Форматирование, пробелы, кавычки |
| `chore` | Обновление зависимостей, конфигов |
| `perf` | Оптимизация производительности |
| `ci` | Правки в CI/CD |

### Примеры хороших коммитов

```bash
feat(orders): добавить защиту от overselling через F-выражения
fix(users): исправить падение при регистрации с деактивированным email
refactor(products): вынести фильтры каталога в products/services.py
test(reviews): покрыть бизнес-правило «отзыв только после покупки»
docs(readme): добавить примеры запросов с JWT
chore(deps): мигрировать с requirements.txt на Poetry 2.x
ci: обновить workflow под poetry run

# GraphQL-специфика
feat(graphql): добавить аналитический эндпоинт на Strawberry
feat(graphql): реализовать orderMetrics и orderTrends
feat(graphql): защитить аналитику декоратором @staff_only
feat(graphql): кешировать аналитические метрики через @cache_metric
fix(graphql): использовать timezone.localdate() вместо timezone.now().date()
fix(graphql): квантизовать Decimal до 2 знаков в денежных резолверах
test(graphql): покрыть права доступа и orderMetrics
test(graphql): покрыть кеш метрик и порядок проверки прав
docs(readme): описать схему и примеры запросов в README

# Redis / кеш
feat(cache): подключить Redis как backend для кеша аналитики
chore(deps): добавить redis для кеша аналитических метрик
chore(infra): поднять Redis в docker-compose и CI

# Pre-commit / Makefile
chore: настроить pre-commit hooks
chore: добавить Makefile со шорткатами для типовых команд
chore(ci): обновить pre-commit hooks
```

### Примеры плохих коммитов

```bash
fix                       # нечего не говорит
WIP                       # черновик
update files              # какие файлы? что обновил?
Fix bug                   # какой баг?
срочно                    # не по конвенции
add graphql               # без типа и области
```

### Правила

- **Один коммит — одна логическая правка.**
- **Императив**: «добавить», «исправить».
- **Точка в конце не ставится.**
- Первая строка — **до 72 символов**.

---

## Pull Request

### Перед созданием PR

```bash
git fetch origin
git rebase origin/dev_3st_week
```

Прогоните все проверки — минимально:

```bash
make ci
```

Обновите `README.md`, если меняли:
- публичное API (REST или GraphQL),
- переменные окружения (в том числе `REDIS_URL`),
- структуру проекта,
- зависимости.

Обновите `CONTRIBUTING.md`, если добавляли новые команды / процессы (например, новые цели в `Makefile`).

### Шаблон PR

```markdown
## Что сделано

Краткое описание изменений.

## Зачем

Проблема или задача. Ссылка на issue.

## Как проверено

- [ ] Написаны/обновлены тесты
- [ ] `make ci` — зелёный
- [ ] `poetry run pre-commit run --all-files` — зелёный
- [ ] `poetry run ruff check .` — зелёный
- [ ] `poetry run mypy .` — зелёный
- [ ] `poetry run pytest` — все тесты проходят
- [ ] Покрытие ≥ 70%
- [ ] `poetry check --lock` — lock актуален

## Breaking changes

Да / Нет.

Closes #<номер issue>
```

### Ревью

- Минимум **один approve** перед merge.
- Merge — через **Squash & Merge**.

---

## Чек-лист перед push

**Быстрый способ** — через Makefile:

```bash
make ci
```

`make ci` прогоняет:

1. `poetry check --lock` — lock актуален.
2. `ruff check .` — линтер.
3. `ruff format --check .` — форматирование.
4. `mypy .` — типизация.
5. `python manage.py check` — Django system check (включая GraphQL-схему).
6. `python manage.py makemigrations --check --dry-run` — миграции актуальны.
7. `pytest --cov-fail-under=70` — тесты с покрытием.

**Если `make` недоступен** — вручную:

```bash
# 1. Lock-файл актуален
poetry check --lock

# 2. Линтер
poetry run ruff check .
poetry run ruff format --check .

# 3. Типизация
poetry run mypy .

# 4. Django check
poetry run python manage.py check

# 5. Миграции актуальны
poetry run python manage.py makemigrations --check --dry-run

# 6. Тесты
poetry run pytest --ds=config.settings.test
```

**Про pre-commit:** если хуки установлены, шаги 2 и 6 выполняются автоматически при коммите и push. Явный прогон `make ci` нужен для дополнительной уверенности — например, перед PR.

### Полная симуляция CI

**Через Makefile:**

```bash
make up              # поднять db + redis
make ci              # полный прогон всех проверок
```

**Вручную:**

```bash
docker compose up -d db redis

export DJANGO_SETTINGS_MODULE=config.settings.ci
export DJANGO_SECRET_KEY=ci-secret-key-that-is-long-enough-for-hmac-sha256
export POSTGRES_DB=test_db POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost POSTGRES_PORT=5432
export REDIS_URL=redis://localhost:6379/0

poetry run ruff check . && \
poetry run ruff format --check . && \
poetry run mypy . && \
poetry run python manage.py check && \
poetry run python manage.py makemigrations --check --dry-run && \
poetry run python manage.py migrate --noinput && \
poetry run pytest --create-db --migrations --cov-fail-under=70
```

---

## Сообщение об ошибке

### Куда

Создайте [issue](https://github.com/VL-code13/hop/issues/new) с меткой `bug`.

### Что включить

```markdown
## Описание

Что произошло и что вы ожидали.

## Как воспроизвести

1. Зайти на `/products/`
2. Добавить 5 шт. товара в корзину
3. Нажать «Оформить заказ»
4. **Ожидалось:** редирект на страницу оплаты
5. **Получилось:** 500 Internal Server Error

## Окружение

- ОС: Ubuntu 24.04
- Python: 3.12.3
- Poetry: 2.x.x (вывод `poetry --version`)
- Redis: 7.x.x (`redis-cli --version`)
- Ветка: `dev_3st_week`
- Коммит: `a1b2c3d`
- `DJANGO_SETTINGS_MODULE`: `config.settings.development`

## Логи

```
Traceback (most recent call last):
  File "...", line 42, in ...
```
```

### Чего не делать

- Не публикуйте `SECRET_KEY`, пароли, `POSTGRES_PASSWORD`.
- Не прикладывайте `db.sqlite3`.
- Не пишите «всё сломалось» без деталей.

---

## Полезные ссылки

- [README.md](README.md) — общее описание проекта
- [Poetry docs](https://python-poetry.org/docs/) — документация Poetry
- [PEP 621](https://peps.python.org/pep-0621/) — метаданные проекта
- [PEP 735](https://peps.python.org/pep-0735/) — dependency groups
- [PEP 695](https://peps.python.org/pep-0695/) — параметризованные функции и классы
- [pre-commit docs](https://pre-commit.com/) — фреймворк git-хуков
- [GNU Make docs](https://www.gnu.org/software/make/manual/) — документация Makefile
- [Redis docs](https://redis.io/docs/) — документация Redis
- [Django cache framework](https://docs.djangoproject.com/en/stable/topics/cache/) — кеширование в Django
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — CI-пайплайн
- [Django docs](https://docs.djangoproject.com/)
- [DRF docs](https://www.django-rest-framework.org/)
- [Strawberry GraphQL docs](https://strawberry.rocks/) — документация GraphQL-фреймворка
- [strawberry-graphql-django](https://strawberry-graphql-django.readthedocs.io/) — интеграция с Django ORM
- [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0/)

---

**Спасибо за вклад! 🍻**
