"""Settings shared by every environment.

Environment-specific files (local/production/cicd) import everything from
here with ``from .base import *`` and then override what differs.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

env = environ.Env()
env.read_env(BASE_DIR / ".env")  # no-op if the file doesn't exist

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_guid",
    "core",
]

MIDDLEWARE = [
    "django_guid.middleware.guid_middleware",
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Email
# ------------------------------------------------------------------------------
ADMINS = [tuple(x.split(":")) for x in env.list("DJANGO_ADMINS", default=["admin:admin@mail.com"])]
MANAGERS = ADMINS
SERVER_EMAIL = "webapp@ddp-tracker.com"
EMAIL_SUBJECT_PREFIX = "[DDP Tracker] "


# Logging
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    # --- Filters ---
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "request_id": {"()": "django_guid.log_filters.CorrelationId"},
    },
    # --- Formatters ---
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} [{module}.{funcName}:{lineno}] [req:{correlation_id}] {message}",
            "style": "{",
        },
        "simple": {
            "format": "{asctime} {levelname} [req:{correlation_id}] {message}",
            "style": "{",
        },
        "json": {
            "()": "logging.Formatter",
            "format": (
                '{{"time": "{asctime}", "level": "{levelname}", '
                '"logger": "{name}", "module": "{module}", '
                '"request_id": "{correlation_id}", "message": "{message}"}}'
            ),
            "style": "{",
        },
    },
    # --- Handlers ---
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["require_debug_true", "request_id"],
        },
        "console_prod": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": [
                "require_debug_false",
                "request_id",
            ],  # container/systemd log collectors pick this up
        },
        "app_file": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOG_DIR / "app.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["request_id"],
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOG_DIR / "error.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 90,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["request_id"],
        },
        "security_file": {
            "level": "WARNING",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOG_DIR / "security.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 365,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["request_id"],
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false", "request_id"],
            "include_html": False,
        },
    },
    # --- Loggers ---
    "root": {
        "handlers": ["console", "console_prod", "app_file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "console_prod", "app_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["error_file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["security_file", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console", "app_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",  # set to DEBUG temporarily to see SQL queries; noisy in prod
            "propagate": False,
        },
        # Your own app — replace "myapp" with your actual app name(s)
        "core": {
            "handlers": ["console", "console_prod", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
