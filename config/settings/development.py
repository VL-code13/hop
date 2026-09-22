import os

os.environ.setdefault('DJANGO_SECRET_KEY', 'dev-insecure-key-do-not-use-in-prod')

from .base import *

DEBUG = env_bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = ['*'] if DEBUG else os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}