import uuid

from cloudinary.models import CloudinaryField
from django.conf import settings
from django.db import models
from django.urls import reverse


class Clothing(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Type(models.TextChoices):
        TOP = "top", "Top"
        BOTTOM = "bottom", "Bottom"
        DRESS = "dress", "Dress"
        OUTERWEAR = "outerwear", "Outerwear"
        FOOTWEAR = "footwear", "Footwear"
        BAG = "bag", "Bag"
        ACCESSORY = "accessory", "Accessory"
        OTHER = "other", "Other"

    class Size(models.TextChoices):
        XS = "XS", "XS"
        S = "S", "S"
        M = "M", "M"
        L = "L", "L"
        XL = "XL", "XL"
        XXL = "XXL", "XXL"
        OTHER = "other", "Other"

    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like New"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SWAPPED = "swapped", "Swapped"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clothing_items",
        verbose_name="owner",
    )
    name = models.CharField("clothing name", max_length=150)
    description = models.TextField("description")
    image = CloudinaryField("image", blank=True, null=True)
    legacy_image = models.ImageField(
        "legacy image",
        upload_to="clothing/",
        blank=True,
        null=True,
        editable=False,
    )
    type = models.CharField("type", max_length=20, choices=Type.choices)
    size = models.CharField("size", max_length=10, choices=Size.choices)
    condition = models.CharField("condition", max_length=20, choices=Condition.choices)
    status = models.CharField(
        "status",
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "clothing"
        verbose_name_plural = "clothing"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("clothing_catalog:detail", kwargs={"pk": self.pk})

    @property
    def image_url(self):
        if self.image:
            return self.image.url
        if self.legacy_image:
            return self.legacy_image.url
        return ""
