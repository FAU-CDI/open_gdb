"""
Django Docker settings for MemberManagement project.
Reads all relevant setting from the environment
"""

import os
from .settings import *  # pylint: disable=wildcard-import unused-wildcard-import

# No Debugging
# TODO: change this back when done testing!
DEBUG = True

# Minify in production!
HTML_MINIFY = True

# we want to allow all hosts
ALLOWED_HOSTS = os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "").split(",")

# all our sessions be safe
SECRET_KEY = os.environ.setdefault("DJANGO_SECRET_KEY", "")

# Passwords
DATABASES = {
    "default": {
        "ENGINE": os.environ.setdefault("DJANGO_DB_ENGINE", ""),
        "NAME": os.environ.setdefault("DJANGO_DB_NAME", ""),
        "USER": os.environ.setdefault("DJANGO_DB_USER", ""),
        "PASSWORD": os.environ.setdefault("DJANGO_DB_PASSWORD", ""),
        "HOST": os.environ.setdefault("DJANGO_DB_HOST", ""),
        "PORT": os.environ.setdefault("DJANGO_DB_PORT", ""),
    }
}

# staticfiles
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# add the static file root
STATIC_ROOT = "/var/www/static/"

# tell Django we're running as https when using the DJANGO_X_FORWARDED_HEADER variable
if len(os.environ.setdefault("DJANGO_X_FORWARDED_HEADER", "")) > 0:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
