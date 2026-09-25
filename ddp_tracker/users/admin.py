from django.contrib import admin

from ddp_tracker.users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "date_joined",
        "last_login",
        "is_superuser",
        "is_active",
    ]
