"""Базовые настройки проекта Hop & Barley.

Содержит общие параметры для всех окружений (development, production).
Специфичные настройки баз данных и отладки переопределяются в соседних модулях.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# BASE_DIR указывает на корень проекта (hop-and-barley/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Надежная загрузка .env из корня проекта
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY' )

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Сторонние библиотеки
    'rest_framework',
    'rest_framework_simplejwt', # JWT аутентификация по ТЗ
    
    # Приложения проекта
    'products',
    'orders',
    'users',
    'reviews',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
# File storage configuration
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Email Backend (консоль для dev / логов)
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
#MAILERS = {
#    'default': {
#        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
#    },
#}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Конфигурация сессий (раздел 3.3 ТЗ: корзина в сессиях)
CART_SESSION_ID: str = 'cart'
SESSION_COOKIE_AGE: int = 60 * 60 * 24 * 30  # 30 дней хранения сессии
SESSION_SAVE_EVERY_REQUEST: bool = False

# Маршруты авторизации пользователей (раздел 3.5 ТЗ)
LOGIN_URL: str = 'users:login'
LOGIN_REDIRECT_URL: str = 'products:list'
LOGOUT_REDIRECT_URL: str = 'products:list'

# Email-уведомления (раздел 3.4 ТЗ)
EMAIL_BACKEND: str = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL: str = 'Hop & Barley <noreply@hopandbarley.com>'
ADMINS: list[tuple[str, str]] = [
    ('Shop Admin', 'admin@hopandbarley.com'),
]

# Конфигурация Django REST Framework (разделы 2 и 3.7 ТЗ)
REST_FRAMEWORK: dict[str, object] = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# Настройки JWT-аутентификации SimpleJWT
SIMPLE_JWT: dict[str, object] = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}