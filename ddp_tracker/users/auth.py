from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from ddp_tracker.users.models import User


def signed_in_user(request: HttpRequest) -> User:
    """The request's user, for views behind ``login_required`` (typed, unlike ``request.user``)."""
    user = request.user
    if isinstance(user, AnonymousUser):
        raise PermissionDenied
    return user
