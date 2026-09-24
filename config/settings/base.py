"""Базовые настройки проекта Hop & Barley.

Содержит общие параметры для всех окружений (development, production).
Специфичные настройки баз данных и отладки переопределяются в соседних модулях.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# BASE_DIR указывает на корень проекта (hop-and-barley/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 1. Сначала загружаем .env
load_dotenv(BASE_DIR / '.env')


# 2. Потом читаем любые env-переменные
def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == '':
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


DEBUG = env_bool('DJANGO_DEBUG', default=False)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY не задан. Укажите его в .env или переменных окружения.')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Сторонние библиотеки (разделы 2, 3.7, 3.8 ТЗ)
    'rest_framework',
    'rest_framework_simplejwt',  # JWT аутентификация по ТЗ
    'drf_spectacular',
    'django_filters',
    'strawberry_django',  # интеграция Strawberry с Django ORM
    # Приложения проекта
    'products',
    'orders',
    'users',
    'reviews',
    'payments',
]

# Настройка генератора схемы REST Framework и фильтрации
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 9,
}

# Метаданные OpenAPI документации (раздел 3.8 ТЗ)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Hop & Barley API',
    'DESCRIPTION': 'REST API интернет-магазина товаров для крафтового пивоварения Hop & Barley.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'config.graphql.middleware.GraphQLJWTAuthMiddleware',  # JWT для /graphql/
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Контекстный процессор сессионной корзины для счетчика в base.html
                'orders.context_processors.cart',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Статика и Медиа
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File storage configuration (WhiteNoise сжатие и хеширование)
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if ('test' in sys.argv or 'pytest' in sys.modules)
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}
# Также можно отключить строгость поиска по манифесту:
WHITENOISE_MANIFEST_STRICT = False
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─────────────────────────────────────────────────────────────────────────────
# Кеширование (Redis) — раздел 3.9 ТЗ, кеш аналитических метрик GraphQL
# ─────────────────────────────────────────────────────────────────────────────
# Redis используется через django.core.cache.backends.redis.RedisCache —
# декоратор @cache_metric (config/graphql/cache.py) не знает про конкретный
# backend, работает с django.core.cache. Смена backend — только здесь.
#
# Fallback на LocMemCache, если REDIS_URL не задан:
#   - удобно для локальной разработки без Redis;
#   - в тестах (config.settings.test) всегда LocMemCache — см. test.py;
#   - в prod Redis обязателен (fail-fast в config.settings.prod).
#
# ВАЖНО: LocMemCache живёт в памяти процесса. При нескольких воркерах
# gunicorn каждый процесс имеет свой кеш — метрика, закешированная в
# одном воркере, не видна в другом. Для продакшена обязательно Redis.
REDIS_URL = os.getenv('REDIS_URL')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'hopbarley',
            'TIMEOUT': 300,  # 5 минут — дефолт для всех ключей
        },
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'hopbarley-cache',
        },
    }
# ─────────────────────────────────────────────────────────────────────────────
# Celery — фоновые задачи
# ─────────────────────────────────────────────────────────────────────────────
# Redis используется как брокер (отдельная БД от кеша, чтобы cache.clear()
# не уничтожал очередь задач).
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

# Формат сериализации — JSON безопаснее pickle (нет RCE-рисков)
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

# Таймзона для расписания
CELERY_TIMEZONE = TIME_ZONE  # уже есть в settings

# Retry политика для email-задач
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Конфигурация сессий (раздел 3.3 ТЗ: корзина в сессиях)
CART_SESSION_ID: str = 'cart'
SESSION_COOKIE_AGE: int = 60 * 60 * 24 * 30  # 30 дней хранения сессии
SESSION_SAVE_EVERY_REQUEST: bool = False

# Маршруты авторизации пользователей (раздел 3.5 ТЗ)
LOGIN_URL: str = 'users:login'
LOGIN_REDIRECT_URL: str = 'products:product_list'
LOGOUT_REDIRECT_URL: str = 'products:product_list'

# Email-уведомления и почтовые службы (раздел 3.4 ТЗ)
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    'Hop & Barley <noreply@hopandbarley.com>',
)

# Список администраторов (кортежи: имя, email)
ADMINS = [
    ('Admin', 'admin@hopandbarley.com'),
]

# Настройки JWT-аутентификации SimpleJWT
SIMPLE_JWT: dict[str, object] = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

AUTHENTICATION_BACKENDS = [
    'users.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]
