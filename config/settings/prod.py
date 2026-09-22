from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = env_bool('DJANGO_DEBUG', default=False)  # в prod False по умолчанию
if DEBUG and not env_bool('ALLOW_DEBUG_IN_PROD', default=False):
    raise ImproperlyConfigured(
        'DEBUG=True с config.settings.prod. Установите DJANGO_DEBUG=False или ALLOW_DEBUG_IN_PROD=1 (для отладки).'
    )
ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'example.com').split(',') if h.strip()]
WHITENOISE_MANIFEST_STRICT = not DEBUG
# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'hopbarley'),
        'USER': os.getenv('POSTGRES_USER', 'user'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'p@ssword123'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}
