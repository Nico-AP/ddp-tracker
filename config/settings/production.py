"""Production settings.

Everything security- or environment-sensitive is required from the
environment with no default, so a misconfigured deploy fails fast at
startup instead of silently running insecurely.
"""

from csp.constants import NONCE, NONE, SELF

from .base import *
from .base import env

DEBUG = False

SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 7)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


# Content security policy (CSP)
# ------------------------------------------------------------------------------
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [NONE],
        "script-src": [SELF, NONCE],
        "style-src": [SELF],
        "img-src": [SELF, "data:"],
        "font-src": [SELF],
        "connect-src": [SELF],
        "form-action": [SELF],
        "frame-ancestors": [NONE],
        "base-uri": [NONE],
        "object-src": [NONE],
        "upgrade-insecure-requests": True,
    },
}
