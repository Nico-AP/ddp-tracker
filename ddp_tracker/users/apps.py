from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ddp_tracker.users"
    verbose_name = "DDP Tracker Users"
