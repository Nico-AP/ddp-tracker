from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.http import HttpRequest, HttpResponseBase


class PrivateModeMiddleware(LoginRequiredMiddleware):
    """With ``settings.PRIVATE_MODE``, every view needs a login unless it is marked
    ``login_not_required`` (the landing page, the health check, logging in)."""

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable[..., HttpResponseBase],
        view_args: tuple[Any, ...],
        view_kwargs: dict[str, Any],
    ) -> HttpResponseBase | None:
        if not settings.PRIVATE_MODE:
            return None
        return super().process_view(request, view_func, view_args, view_kwargs)
