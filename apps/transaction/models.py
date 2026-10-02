from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Transaction(models.Model):
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

    def __str__(self):
        return f"Transaction {self.id} - {self.status}"

    def clean(self):
        if self.method == self.Method.DELIVERY:
            if not self.requester_resi:
                raise ValidationError(
                    {"requester_resi": ("Requester resi is required for delivery.")}
                )

            if not self.requester_delivery_estimate:
                raise ValidationError(
                    {
                        "requester_delivery_estimate": (
                            "Delivery estimate is required for delivery."
                        )
                    }
                )

        elif self.method == self.Method.MEETUP:
            if not self.meetup_date:
                raise ValidationError(
                    {"meetup_date": ("Meetup date is required for meetup.")}
                )

            if not self.meetup_location:
                raise ValidationError(
                    {"meetup_location": ("Meetup location is required for meetup.")}
                )

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
