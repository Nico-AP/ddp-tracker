"""Settings for local development on a developer's machine."""

from .base import *
from .base import env

DEBUG = True

SECRET_KEY = env.str(
    "DJANGO_SECRET_KEY",
    default="django-insecure-local-dev-key-do-not-use-in-production",
)

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


# django-debug-toolbar - https://github.com/django-commons/django-debug-toolbar
# ------------------------------------------------------------------------------
if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
    DEBUG_TOOLBAR_CONFIG = {
        "DISABLE_PANELS": [
            "debug_toolbar.panels.redirects.RedirectsPanel",
            # Disable profiling panel due to an issue with Python 3.12:
            # https://github.com/jazzband/django-debug-toolbar/issues/1875
            "debug_toolbar.panels.profiling.ProfilingPanel",
        ],
        "SHOW_TEMPLATE_CONTEXT": True,
    }
    INTERNAL_IPS = ["127.0.0.1"]
