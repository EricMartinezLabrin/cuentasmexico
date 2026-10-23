"""Isolated SQLite settings for shop-map tests; never connects to configured MySQL."""
from CuentasMexico.settings import *  # noqa: F401,F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
# Legacy repository migration history differs from current models and includes MySQL SQL.
# Feature tests use synchronized models; migration operations are tested separately.
MIGRATION_MODULES = {label: None for label in ('adm', 'cupon', 'index', 'api', 'api_bot', 'ThanksYou')}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
