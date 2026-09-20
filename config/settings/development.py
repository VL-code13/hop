from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# Временная БД для локальной разработки
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
