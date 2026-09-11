"""Settings used by CI (GitHub Actions) to lint and run the test suite.

Deliberately dependency-free: in-memory SQLite, no external services, no
secrets to provision.
"""

from .base import *

DEBUG = False

SECRET_KEY = "django-insecure-cicd-key-not-for-production"  # noqa: S105

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
