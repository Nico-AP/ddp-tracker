from django.db import migrations

# Activities named as what the actor did ("viewed", not "view"). Existing rows are renamed in
# place, so representations keep their activity.
RENAMED = {
    "view": ("viewed", "viewed", "The actor has viewed the object."),
    "open": ("opened", "opened", "The actor opened the object, e.g. an app or a link."),
    "listen": ("listened", "listened", "The actor has listened to the object."),
    "create": ("created", "created", "The actor has created the object."),
    "follow": ("followed", "followed", "The actor is following the object, e.g. an account."),
    "block": ("blocked", "blocked", "The actor is blocking the object."),
    "join": ("joined", "joined", "The actor has joined the object, e.g. a group or live."),
    "update": ("updated", "updated", "The actor has changed the object."),
    "question": ("asked", "asked", "The actor asked a question."),
    "add": ("added", "added", "The actor has added the object to the target."),
}
ADDED = {
    "responded": ("responded", "The actor responded to the object."),
    "searched": ("searched", "The actor has searched for the object."),
}
# what 0002 seeded, to rename back
ORIGINAL = {
    "view": ("view", "The actor has viewed the object."),
    "open": ("open", "The actor opened the object, e.g. an app or a link."),
    "listen": ("listen", "The actor has listened to the object."),
    "create": ("create", "The actor has created the object."),
    "follow": ("follow", "The actor is following the object, e.g. an account."),
    "block": ("block", "The actor is blocking the object."),
    "join": ("join", "The actor has joined the object, e.g. a group or live."),
    "update": ("update", "The actor has changed the object."),
    "question": ("question", "The actor asked a question, e.g. a poll."),
    "add": ("add", "The actor has added the object to the target."),
}


def rename(apps, schema_editor):
    ActivityType = apps.get_model("representations", "ActivityType")
    for old, (slug, name, description) in RENAMED.items():
        if not ActivityType.objects.filter(slug=slug).exists():
            ActivityType.objects.filter(slug=old).update(
                slug=slug, name=name, description=description
            )
    for slug, (name, description) in {**ADDED, "asked": RENAMED["question"][1:]}.items():
        ActivityType.objects.get_or_create(
            slug=slug, defaults={"name": name, "description": description, "approved": True}
        )


def rename_back(apps, schema_editor):
    ActivityType = apps.get_model("representations", "ActivityType")
    ActivityType.objects.filter(
        slug__in=ADDED, created_by=None, representations__isnull=True
    ).delete()
    for old, (slug, _, _) in RENAMED.items():
        name, description = ORIGINAL[old]
        ActivityType.objects.filter(slug=slug).update(slug=old, name=name, description=description)


class Migration(migrations.Migration):
    dependencies = [
        ("representations", "0002_seed_vocabularies"),
    ]

    operations = [
        migrations.RunPython(rename, rename_back),
    ]
