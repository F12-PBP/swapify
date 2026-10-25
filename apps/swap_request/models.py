from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.urls import reverse

from apps.clothing_catalog.models import Clothing


class SwapRequestQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(Q(requester=user) | Q(requested_clothing__owner=user))


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

        constraints = [
            models.CheckConstraint(
                condition=~Q(requested_clothing=F("offered_clothing")),
                name="canonical_swap_distinct_clothing",
            ),
        ]

    def __str__(self):
        return f"{self.offered_clothing} -> {self.requested_clothing}"

    def get_absolute_url(self):
        return reverse("swap_request:detail", kwargs={"pk": self.pk})

    @property
    def owner(self):
        return self.requested_clothing.owner

    objects = SwapRequestQuerySet.as_manager()

    def is_participant(self, user):
        return user.is_authenticated and user.pk in (
            self.requester_id,
            self.requested_clothing.owner_id,
        )

    def clean(self):
        super().clean()

        if not (self.requested_clothing_id and self.offered_clothing_id):
            return

        if self.requested_clothing_id == self.offered_clothing_id:
            raise ValidationError("Requested and offered clothing must be different.")

        if self.requested_clothing.owner_id == self.requester_id:
            raise ValidationError("You cannot request your own clothing.")

        if self.offered_clothing.owner_id != self.requester_id:
            raise ValidationError("Offered clothing must belong to the requester.")
