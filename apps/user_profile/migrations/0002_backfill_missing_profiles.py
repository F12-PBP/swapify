from django.conf import settings
from django.db import migrations


def backfill_missing_profiles(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Profile = apps.get_model("user_profile", "Profile")
    alias = schema_editor.connection.alias
    users = (
        User.objects.using(alias)
        .filter(profile__isnull=True)
        .values_list("pk", "username")
    )
    for user_id, username in users.iterator():
        Profile.objects.using(alias).get_or_create(
            user_id=user_id, defaults={"display_name": username}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("user_profile", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(backfill_missing_profiles, migrations.RunPython.noop),
    ]
