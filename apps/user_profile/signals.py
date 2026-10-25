from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    Profile.objects.get_or_create(
        user=instance, defaults={"display_name": instance.get_username()}
    )
