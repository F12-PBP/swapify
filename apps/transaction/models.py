import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    swap_request = models.OneToOneField(
        "swap_request.SwapRequest",
        on_delete=models.PROTECT,
        related_name="transaction",
    )

    class Method(models.TextChoices):
        MEETUP = "Meetup", "Meetup"
        DELIVERY = "Delivery", "Delivery"

    class Status(models.TextChoices):
        WAITING = "Waiting", "Waiting"
        IN_PROGRESS = "InProgress", "In Progress"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"
        DISPUTED = "Disputed", "Disputed"

    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.MEETUP,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )

    # Requester's delivery information
    requester_courier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    requester_resi = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    requester_delivery_estimate = models.DateTimeField(
        null=True,
        blank=True,
    )

    requester_resi_valid = models.BooleanField(
        default=False,
    )

    requester_received = models.BooleanField(
        default=False,
    )

    requester_received_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Owner's delivery information
    owner_courier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    owner_resi = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    owner_delivery_estimate = models.DateTimeField(
        null=True,
        blank=True,
    )

    owner_resi_valid = models.BooleanField(
        default=False,
    )

    owner_received = models.BooleanField(
        default=False,
    )

    owner_received_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Meetup information
    meetup_date = models.DateTimeField(
        null=True,
        blank=True,
    )

    meetup_location = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    reported_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Start Parameter
    requester_started = models.BooleanField(
        default=False,
    )

    owner_started = models.BooleanField(
        default=False,
    )

    def __str__(self):
        return f"Transaction {self.id} - {self.status}"

    def clean(self):
        super().clean()

        if self.status not in (self.Status.IN_PROGRESS, self.Status.COMPLETED):
            return

        errors = {}
        if self.method == self.Method.DELIVERY:
            for party in ("requester", "owner"):
                if not (getattr(self, f"{party}_resi") or "").strip():
                    errors[f"{party}_resi"] = (
                        f"{party.capitalize()} tracking number is required "
                        "for delivery."
                    )
                if not getattr(self, f"{party}_delivery_estimate"):
                    errors[f"{party}_delivery_estimate"] = (
                        f"{party.capitalize()} delivery estimate is required."
                    )

        elif self.method == self.Method.MEETUP:
            if not self.meetup_date:
                errors["meetup_date"] = "Meetup date is required for meetup."

            if not (self.meetup_location or "").strip():
                errors["meetup_location"] = "Meetup location is required for meetup."

        if errors:
            raise ValidationError(errors)

    @property
    def is_overdue(self):
        if self.status != self.Status.IN_PROGRESS:
            return False

        now = timezone.now()
        buffer_time = timedelta(days=2)

        requester_waiting = (
            not self.requester_received
            and self.owner_delivery_estimate
            and now > self.owner_delivery_estimate + buffer_time
        )

        owner_waiting = (
            not self.owner_received
            and self.requester_delivery_estimate
            and now > self.requester_delivery_estimate + buffer_time
        )

        return requester_waiting or owner_waiting

    @property
    def requester(self):
        return self.swap_request.requester

    @property
    def owner(self):
        return self.swap_request.owner

    def is_participant(self, user):
        return self.swap_request.is_participant(user)
