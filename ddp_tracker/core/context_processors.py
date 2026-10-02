from django.conf import settings
from django.http import HttpRequest


def site_flags(request: HttpRequest) -> dict[str, bool]:
    """The invite-only switches the templates need."""
    return {
        "DEV_BANNER": settings.DEV_BANNER,
        "PRIVATE_MODE": settings.PRIVATE_MODE,
    }
