from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from ddp_tracker.users.auth import signed_in_user
from ddp_tracker.users.models import User


class AuthTests(TestCase):
    def test_signed_in_user(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            signed_in_user(request)
        request.user = User(email="x@example.com")
        self.assertEqual(signed_in_user(request).email, "x@example.com")


class SignupTests(TestCase):
    data = {
        "email": "new@example.org",
        "password1": "a-long-pass-phrase",
        "password2": "a-long-pass-phrase",
    }

    def test_closed_by_default(self):
        url = reverse("account_signup")
        self.assertTemplateUsed(self.client.get(url), "account/signup_closed.html")
        response = self.client.post(url, self.data)
        self.assertTemplateUsed(response, "account/signup_closed.html")
        self.assertContains(response, "only open to invited users")
        self.assertFalse(User.objects.exists())

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=True)
    def test_open_when_switched_on(self):
        response = self.client.get(reverse("account_signup"))
        self.assertTemplateUsed(response, "account/signup.html")
