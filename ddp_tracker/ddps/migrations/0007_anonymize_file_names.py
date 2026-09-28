from django.db import migrations

from ddp_tracker.ddps.names import anonymize_file_name


def anonymize(apps, schema_editor):
    """File names of earlier uploads are stored anonymized too (ddps/names.py): the upload's own,
    and the one the parser copied into the document (source and root node)."""
    Upload = apps.get_model("ddps", "Upload")
    for upload in Upload.objects.only("file_name", "document").iterator():
        upload.file_name = anonymize_file_name(upload.file_name)
        document = upload.document or {}
        for part in ("source", "root"):
            node = document.get(part)
            if isinstance(node, dict) and node.get("name"):
                node["name"] = anonymize_file_name(node["name"])
        upload.save(update_fields=["file_name", "document"])


class Migration(migrations.Migration):
    dependencies = [
        ("ddps", "0006_upload_values"),
    ]

    operations = [
        migrations.RunPython(anonymize, migrations.RunPython.noop),
    ]
