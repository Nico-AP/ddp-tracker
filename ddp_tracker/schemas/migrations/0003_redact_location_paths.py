from django.db import migrations

from ddp_tracker.schemas.migrate_paths import redact_stored_paths


class Migration(migrations.Migration):
    dependencies = [
        ("schemas", "0002_example_sources"),
        ("ddps", "0010_request_format_choices"),
        ("proposals", "0002_representation_kinds"),
        ("representations", "0005_location"),
    ]

    operations = [
        migrations.RunPython(redact_stored_paths, migrations.RunPython.noop),
    ]
