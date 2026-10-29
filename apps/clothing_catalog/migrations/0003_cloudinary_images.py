import cloudinary.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("clothing_catalog", "0002_align_clothing_with_erd")]

    operations = [
        migrations.RenameField(
            model_name="clothing", old_name="image", new_name="legacy_image"
        ),
        migrations.AlterField(
            model_name="clothing",
            name="legacy_image",
            field=models.ImageField(
                "legacy image",
                upload_to="clothing/",
                blank=True,
                null=True,
                editable=False,
            ),
        ),
        migrations.AddField(
            model_name="clothing",
            name="image",
            field=cloudinary.models.CloudinaryField(
                "image", max_length=255, blank=True, null=True
            ),
        ),
    ]
