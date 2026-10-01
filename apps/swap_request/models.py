from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.clothing_catalog.models import Clothing


class SwapRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Menunggu"
        ACCEPTED = "accepted", "Diterima"
        REJECTED = "rejected", "Ditolak"
        CANCELLED = "cancelled", "Dibatalkan"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_swap_requests",
        verbose_name="pengaju",
    )
    requested_clothing = models.ForeignKey(
        Clothing,
        on_delete=models.CASCADE,
        related_name="incoming_swap_requests",
        verbose_name="pakaian yang diminta",
    )
    offered_clothing = models.ForeignKey(
        Clothing,
        on_delete=models.CASCADE,
        related_name="offered_swap_requests",
        verbose_name="pakaian yang ditawarkan",
    )
    message = models.TextField("pesan", blank=True)
    status = models.CharField(
        "status",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "swap request"
        verbose_name_plural = "swap request"

    def __str__(self):
        return f"{self.offered_clothing} -> {self.requested_clothing}"

    def get_absolute_url(self):
        return reverse("swap_request:detail", kwargs={"pk": self.pk})

    @property
    def owner(self):
        return self.requested_clothing.owner
