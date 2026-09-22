# Contributing to Hop & Barley

Спасибо за интерес к проекту! Этот документ описывает процесс разработки, стандарты кода и требования к изменениям.

## Содержание

- [Кодекс поведения](#кодекс-поведения)
- [Настройка окружения](#настройка-окружения)
- [Git workflow](#git-workflow)
- [Стандарты кода](#стандарты-кода)
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
| PostgreSQL | 16 (для тестов и продакшена) |
| Docker | 24+ (опционально, для БД) |
| Git | 2.40+ |

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/VL-code13/hop.git
cd hop

# 2. Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать .env из шаблона
cp .env.example .env
# Отредактируйте DJANGO_SECRET_KEY (можно сгенерировать):
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

# 5. Применить миграции
python manage.py migrate

# 6. Создать администратора
python manage.py createsuperuser

# 7. Запустить сервер разработки
python manage.py runserver
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

### Создание ветки под задачу

```bash
# Всегда от свежей dev-ветки
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
- **Комментарии** — только для объяснения «почему», а не «что». Код должен говорить сам за себя.

### Линтеры и форматтеры

Проект использует **Ruff** (замена flake8 + isort + black) и **Mypy**.

```bash
# Проверка
ruff check .
ruff format --check .
mypy .

# Автоисправление
ruff check . --fix
ruff format .
```

### Стиль кода

- Кавычки — **одинарные** (`'string'`), кроме случаев, когда внутри есть одинарные.
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

---

## Тестирование

### Минимальные требования к PR

- Новый функционал **обязан** иметь тесты.
- Багфиксы сопровождаются **регрессионным тестом**.
- Покрытие не должно падать (`--cov-fail-under=70`).

### Запуск тестов

```bash
# Быстро, на SQLite
DJANGO_SECRET_KEY=dev pytest --ds=config.settings.development -q --no-cov

# Как в CI, на PostgreSQL
docker compose up -d db
DJANGO_SECRET_KEY=ci-secret-key pytest --create-db --migrations
```

### Структура тестов

- **Модульные тесты** — в `tests.py` соответствующего приложения.
- **Сервисные тесты** — в `tests_services.py` (без HTTP-клиента).
- **Фикстуры** — в глобальном `conftest.py`.

---

## Коммиты

### Формат сообщения

Соблюдаем [Conventional Commits](https://www.conventionalcommits.org/):

```
<тип>(<область>): <краткое описание>

<опциональное тело: почему, а не что>

<опциональные футеры: Closes #123>
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
chore(deps): обновить Django до 6.1.1
```

### Примеры плохих коммитов

```bash
fix                       # нечего не говорит
WIP                       # черновик, не должен попадать в main
update files              # какие файлы? что обновил?
Fix bug                   # какой баг?
срочно                    # не по конвенции
```

### Правила

- **Один коммит — одна логическая правка.** Не смешивайте фичу, рефакторинг и стиль.
- **Императив в описании**: «добавить», «исправить», а не «добавил», «исправил».
- **Точка в конце не ставится.**
- Первая строка — **до 72 символов**.

---

## Pull Request

### Перед созданием PR

1. Убедитесь, что ваша ветка синхронизирована с `dev_3st_week`:

```bash
git fetch origin
git rebase origin/dev_3st_week
```

2. Прогоните все проверки (см. [чек-лист](#чек-лист-перед-push)).

3. Обновите `README.md`, если меняли:
   - публичное API,
   - переменные окружения,
   - структуру проекта.

### Шаблон PR

```markdown
## Что сделано

Краткое описание изменений в 1–3 предложениях.

## Зачем

Проблема или задача, которую решает PR. Ссылка на issue, если есть.

## Как проверено

- [ ] Написаны/обновлены тесты
- [ ] `ruff check .` — зелёный
- [ ] `ruff format --check .` — зелёный
- [ ] `mypy .` — зелёный
- [ ] `pytest` — все тесты проходят
- [ ] Покрытие ≥ 70%
- [ ] Проверено вручную в браузере (если UI)

## Скриншоты (если UI)

| Было | Стало |
|------|-------|
| ![](before.png) | ![](after.png) |

## Breaking changes

Да / Нет. Если да — описать, что сломается.

Closes #<номер issue>
```

### Ревью

- Минимум **один approve** перед merge (для соло-проекта — self-review через GitHub).
- Все комментарии ревьюера должны быть resolved.
- Merge — через **Squash & Merge**, чтобы не засорять историю мелкими коммитами.

---

## Чек-лист перед push

```bash
# 1. Линтер
ruff check .
ruff format --check .

# 2. Типизация
DJANGO_SECRET_KEY=dev DJANGO_SETTINGS_MODULE=config.settings.development mypy .

# 3. Django check
python manage.py check

# 4. Миграции актуальны
python manage.py makemigrations --check --dry-run

# 5. Тесты
DJANGO_SECRET_KEY=dev pytest --ds=config.settings.development -q
```

Если **все пять** зелёные — можно пушить. Если что-то красное — правьте локально.

### Полная симуляция CI

```bash
docker compose up -d db

export DJANGO_SETTINGS_MODULE=config.settings.ci
export DJANGO_SECRET_KEY=ci-secret-key
export POSTGRES_DB=test_db POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost POSTGRES_PORT=5432

ruff check . && ruff format --check . && mypy . && \
python manage.py check && \
python manage.py makemigrations --check --dry-run && \
python manage.py migrate --noinput && \
pytest --create-db --migrations --cov-fail-under=70
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
- Ветка: `dev_3st_week`
- Коммит: `a1b2c3d`
- `DJANGO_SETTINGS_MODULE`: `config.settings.development`

## Логи

```
Traceback (most recent call last):
  File "...", line 42, in ...
```

## Скриншоты

Если применимо.
```

### Чего не делать

- Не публикуйте `SECRET_KEY`, пароли, `POSTGRES_PASSWORD` — даже учебные.
- Не прикладывайте `db.sqlite3` — вместо этого дайте шаги воспроизведения.
- Не пишите «всё сломалось» без деталей — issue будет закрыт как «needs reproduction».

---

## Полезные ссылки

- [README.md](README.md) — общее описание проекта
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — CI-пайплайн
- [Django docs](https://docs.djangoproject.com/)
- [DRF docs](https://www.django-rest-framework.org/)
- [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0/)

---

**Спасибо за вклад! 🍻**