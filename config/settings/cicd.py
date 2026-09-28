"""Settings used by CI (GitHub Actions) to lint and run the test suite.

Deliberately dependency-free by default: in-memory SQLite, no external services,
no secrets to provision. Set ``DATABASE_URL`` to run against another database
(CI's PostgreSQL job does, to catch differences such as jsonb's key order).
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from .base import *  # after the database default above

DEBUG = False

SECRET_KEY = "django-insecure-cicd-key-not-for-production"  # noqa: S105

ALLOWED_HOSTS = ["*"]
