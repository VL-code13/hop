from .base import *  # noqa: F403, F401

DEBUG = True
ALLOWED_HOSTS = ['*']

# Временная БД для локальной разработки
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}
