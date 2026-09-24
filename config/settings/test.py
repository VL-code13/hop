"""Настройки для pytest и CI.

Импортирует всё из base.py и переопределяет только то, что нужно
для быстрых и изолированных тестов:

- MD5-хешер паролей — быстрее в 10–20 раз при создании фикстур.
- LocMemCache — кеш не должен шариться между тестами.
- Locmem email — письма не уходят никуда, их можно проверить в mailoutbox.
- Whitnoise убираем из MIDDLEWARE — статика в тестах не проверяется,
  а он шумит warning'ом при отсутствии папки staticfiles/.
- Пароль-валидаторы отключены — тестовые пароли вида 'testpass123'
  не должны проходить реальную валидацию.
"""

from .base import *  # noqa: F401, F403

# ─── Отладочный режим ───
DEBUG = False
ALLOWED_HOSTS = ['*']

# ─── БД: SQLite в памяти для скорости ───
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}
# Тесты выполняют задачи Celery синхронно (без воркера)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True  # исключения из задач всплывают в тест

# ─── Кеш: локальный in-memory, не шарится между процессами ───
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    },
}

# ─── Email: пишем в память, читаем через fixture `mailoutbox` ───
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# ─── Убираем whitenoise из MIDDLEWARE (в тестах не нужен) ───
MIDDLEWARE = [m for m in MIDDLEWARE if 'whitenoise' not in m.lower()]  # noqa: F405

# ─── Считаем статику обычным хранилищем ───
# CompressedManifestStaticFilesStorage требует собранной статики,
# а в тестах collectstatic не запускается — берём простой backend.
STORAGES = {
    **STORAGES,  # noqa: F405
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

# ─── Быстрый хешер паролей для тестов ───
# MD5 без соли — на порядок быстрее стандартного PBKDF2.
# В продакшене, разумеется, так делать нельзя.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# ─── Отключаем SSL-редирект, чтобы тестовый клиент ходил по HTTP ───
SECURE_SSL_REDIRECT = False

# ─── Отключаем security-заголовки, которые мешают тестам ───
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
