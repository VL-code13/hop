# Contributing to Hop & Barley

Спасибо за интерес к проекту! Этот документ описывает процесс разработки, стандарты кода и требования к изменениям.

## Содержание

- [Кодекс поведения](#кодекс-поведения)
- [Настройка окружения](#настройка-окружения)
- [Git workflow](#git-workflow)
- [Стандарты кода](#стандарты-кода)
- [Управление зависимостями (Poetry)](#управление-зависимостями-poetry)
- [Тестирование](#тестирование)
- [Коммиты](#коммиты)
- [Pull Request](#pull-request)
- [Чек-лист перед push](#чек-лист-перед-push)
- [Сообщение об ошибке](#сообщение-об-ошибке)

---

## Кодекс поведения

- Будьте уважительны в комментариях и ревью.
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
| Docker | 24+ (опционально, для БД) |
| Git | 2.40+ |

**Установка Poetry** (если не установлена):

```bash
pipx install poetry
# или
curl -sSL https://install.python-poetry.org | python3 -
```

### Установка проекта

```bash
# 1. Клонировать репозиторий
git clone https://github.com/VL-code13/hop.git
cd hop

# 2. Установить все зависимости (main + dev)
poetry install

# 3. Создать .env из шаблона
cp .env.example .env
# Отредактируйте DJANGO_SECRET_KEY:
poetry run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

# 4. Применить миграции
poetry run python manage.py migrate

# 5. Создать администратора
poetry run python manage.py createsuperuser

# 6. Запустить сервер разработки
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

### Docker (опционально, для PostgreSQL)

```bash
docker compose up -d db           # только БД
docker compose up --build -d      # весь стек
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
    ...
]

[dependency-groups]
dev = [
    "pytest==9.1.1",
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

```bash
# Быстро, на SQLite in-memory
poetry run pytest --ds=config.settings.test

# Как в CI, на PostgreSQL
docker compose up -d db
poetry run pytest --ds=config.settings.ci --create-db --migrations

# Только GraphQL-тесты, быстро (без coverage)
poetry run pytest tests/graphql/ --ds=config.settings.test --no-cov -v

# С покрытием
poetry run pytest --ds=config.settings.test --cov=. --cov-report=html
```

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
  - `_clear_cache` (autouse) — сбрасывает кеш до и после каждого теста. Без неё `LocMemCache` живёт между тестами и ломает изоляцию: тест, прогревающий аналитический резолвер, «протечёт» в следующий тест и вернёт устаревшие данные.

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

Прогоните все проверки (см. [чек-лист](#чек-лист-перед-push)).

Обновите `README.md`, если меняли:
- публичное API (REST или GraphQL),
- переменные окружения,
- структуру проекта,
- зависимости.

### Шаблон PR

```markdown
## Что сделано

Краткое описание изменений.

## Зачем

Проблема или задача. Ссылка на issue.

## Как проверено

- [ ] Написаны/обновлены тесты
- [ ] `poetry run ruff check .` — зелёный
- [ ] `poetry run ruff format --check .` — зелёный
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

```bash
# 1. Линтер
poetry run ruff check .
poetry run ruff format --check .

# 2. Типизация
poetry run mypy .

# 3. Django check
poetry run python manage.py check

# 4. Миграции актуальны
poetry run python manage.py makemigrations --check --dry-run

# 5. Lock-файл актуален
poetry check --lock

# 6. Тесты
poetry run pytest --ds=config.settings.test
```

Если **все шесть** зелёные — можно пушить.

### Полная симуляция CI

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
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — CI-пайплайн
- [Django docs](https://docs.djangoproject.com/)
- [DRF docs](https://www.django-rest-framework.org/)
- [Strawberry GraphQL docs](https://strawberry.rocks/) — документация GraphQL-фреймворка
- [strawberry-graphql-django](https://strawberry-graphql-django.readthedocs.io/) — интеграция с Django ORM
- [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0/)

---

**Спасибо за вклад! 🍻**