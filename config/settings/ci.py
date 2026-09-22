# ci.py — задаём fallback в env ДО импорта base,
# иначе base.py упадёт на guard'е SECRET_KEY
import os

os.environ.setdefault('DJANGO_SECRET_KEY', 'ci-secret-key')

from .base import *

ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost').split(',') if h.strip()]
WHITENOISE_MANIFEST_STRICT = True

SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'test_db'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
