import uuid

from django.db import migrations, models


def populate_clothing_uuid_keys(apps, schema_editor):
    Clothing = apps.get_model("clothing_catalog", "Clothing")
    database = schema_editor.connection.alias

    clothing_items = Clothing.objects.using(database).filter(uuid_key__isnull=True)
    for clothing in clothing_items.iterator():
        clothing.uuid_key = uuid.uuid4()
        clothing.save(using=database, update_fields=["uuid_key"])


class Migration(migrations.Migration):
    dependencies = [
        ("clothing_catalog", "0004_alter_clothing_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="clothing",
            name="uuid_key",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_clothing_uuid_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="clothing",
            name="uuid_key",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
