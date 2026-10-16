"""Isolated workflow tests never connect to either live laboratory database."""
from .settings import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('EI_TEST_DB_PATH', ':memory:')}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
URL_PREFIX = '/ei-lab'
SESSION_COOKIE_NAME = 'ei_lab_sessionid'
CSRF_COOKIE_NAME = 'ei_lab_csrftoken'
SESSION_COOKIE_PATH = '/ei-lab/'
CSRF_COOKIE_PATH = '/ei-lab/'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
