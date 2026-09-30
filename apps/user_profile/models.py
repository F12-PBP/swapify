# import uuid
from cloudinary.models import CloudinaryField
from django.conf import settings
from django.db import models

# Create your models here.


class Profile(models.Model):
    # id = models.UUIDField("id",default=uuid.uuid4, primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField("display name", max_length=225)
    bio = models.TextField("bio", blank=True)
    profile_picture = CloudinaryField("profile picture", blank=True, null=True)
    latitude = models.FloatField("latitude", null=True, blank=True)
    longitude = models.FloatField("longitude", null=True, blank=True)
    district = models.CharField("district", max_length=225, null=True, blank=True)
    city = models.CharField("city", max_length=225, null=True, blank=True)
    province = models.CharField("province", max_length=225, null=True, blank=True)

    def __str__(self):
        return self.display_name
