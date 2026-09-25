from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from ddp_tracker.users.auth import signed_in_user
from ddp_tracker.users.models import User


class AuthTests(TestCase):
    def test_signed_in_user(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            signed_in_user(request)
        request.user = User(username="x")
        self.assertEqual(signed_in_user(request).username, "x")
