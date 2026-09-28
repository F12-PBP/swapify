from django.conf import settings
from django.db import models
from django.urls import reverse


class Clothing(models.Model):
    class Category(models.TextChoices):
        TOP = "top", "Atasan"
        BOTTOM = "bottom", "Bawahan"
        DRESS = "dress", "Dress"
        OUTERWEAR = "outerwear", "Outerwear"
        FOOTWEAR = "footwear", "Alas kaki"
        OTHER = "other", "Lainnya"

    class Size(models.TextChoices):
        XS = "XS", "XS"
        S = "S", "S"
        M = "M", "M"
        L = "L", "L"
        XL = "XL", "XL"
        XXL = "XXL", "XXL"
        OTHER = "other", "Lainnya"

    class Condition(models.TextChoices):
        NEW = "new", "Baru"
        LIKE_NEW = "like_new", "Seperti baru"
        GOOD = "good", "Baik"
        FAIR = "fair", "Cukup baik"

    class Availability(models.TextChoices):
        AVAILABLE = "available", "Tersedia"
        UNAVAILABLE = "unavailable", "Tidak tersedia"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clothing_items",
        verbose_name="pemilik",
    )
    name = models.CharField("nama pakaian", max_length=150)
    description = models.TextField("deskripsi")
    category = models.CharField("kategori", max_length=20, choices=Category.choices)
    size = models.CharField("ukuran", max_length=10, choices=Size.choices)
    condition = models.CharField("kondisi", max_length=20, choices=Condition.choices)
    availability = models.CharField(
        "status ketersediaan",
        max_length=20,
        choices=Availability.choices,
        default=Availability.AVAILABLE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "pakaian"
        verbose_name_plural = "pakaian"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("clothing_catalog:detail", kwargs={"pk": self.pk})
