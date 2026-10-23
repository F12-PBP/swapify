from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clothing_catalog", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="clothing",
            old_name="category",
            new_name="type",
        ),
        migrations.RenameField(
            model_name="clothing",
            old_name="availability",
            new_name="status",
        ),
        migrations.AddField(
            model_name="clothing",
            name="image",
            field=models.ImageField(
                blank=True, null=True, upload_to="clothing/", verbose_name="image"
            ),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="type",
            field=models.CharField(
                choices=[
                    ("top", "Top"),
                    ("bottom", "Bottom"),
                    ("dress", "Dress"),
                    ("outerwear", "Outerwear"),
                    ("footwear", "Footwear"),
                    ("other", "Other"),
                ],
                max_length=20,
                verbose_name="type",
            ),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="size",
            field=models.CharField(
                choices=[
                    ("XS", "XS"),
                    ("S", "S"),
                    ("M", "M"),
                    ("L", "L"),
                    ("XL", "XL"),
                    ("XXL", "XXL"),
                    ("other", "Other"),
                ],
                max_length=10,
                verbose_name="size",
            ),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="condition",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("like_new", "Like New"),
                    ("good", "Good"),
                    ("fair", "Fair"),
                ],
                max_length=20,
                verbose_name="condition",
            ),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="status",
            field=models.CharField(
                choices=[
                    ("available", "Available"),
                    ("reserved", "Reserved"),
                    ("swapped", "Swapped"),
                ],
                default="available",
                max_length=20,
                verbose_name="status",
            ),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="owner",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="clothing_items",
                to="auth.user",
                verbose_name="owner",
            ),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="name",
            field=models.CharField(max_length=150, verbose_name="clothing name"),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="description",
            field=models.TextField(verbose_name="description"),
        ),
        migrations.AlterModelOptions(
            name="clothing",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "clothing",
                "verbose_name_plural": "clothing",
            },
        ),
    ]
