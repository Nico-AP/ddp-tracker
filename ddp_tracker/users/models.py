from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    username = None  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
