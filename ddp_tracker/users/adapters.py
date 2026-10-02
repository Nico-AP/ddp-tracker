from __future__ import annotations

import typing

from django.conf import settings

from allauth.account.adapter import DefaultAccountAdapter

if typing.TYPE_CHECKING:
    from django.http import HttpRequest


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return settings.ACCOUNT_ALLOW_REGISTRATION
