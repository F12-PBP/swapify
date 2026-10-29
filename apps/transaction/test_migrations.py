import importlib
import uuid
from unittest import skipUnless

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.clothing_catalog.models import Clothing
from apps.review_rating.models import Review
from apps.swap_request.models import SwapRequest

from .models import Transaction

repair_legacy_ids = importlib.import_module(
    "apps.transaction.migrations.0010_repair_sqlite_legacy_transaction_ids"
).repair_legacy_ids


@skipUnless(connection.vendor == "sqlite", "Repairs SQLite's legacy integer IDs.")
class LegacyTransactionIdRepairTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        requester = get_user_model().objects.create_user(username="legacy-requester")
        owner = get_user_model().objects.create_user(username="legacy-owner")
        offered = Clothing.objects.create(
            owner=requester, name="Shirt", type="top", size="M", condition="good"
        )
        requested = Clothing.objects.create(
            owner=owner, name="Jacket", type="outerwear", size="M", condition="good"
        )
        swap = SwapRequest.objects.create(
            requester=requester,
            offered_clothing=offered,
            requested_clothing=requested,
            status=SwapRequest.Status.ACCEPTED,
        )
        cls.exchange = Transaction.objects.create(swap_request=swap)
        cls.review = Review.objects.create(
            transaction=cls.exchange,
            author=requester,
            recipient=owner,
            rating=5,
            comment="Preserve this review.",
        )

    def repair(self):
        repair_legacy_ids(apps, connection.schema_editor())

    def test_repairs_legacy_id_and_review_reference_without_losing_data(self):
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA defer_foreign_keys = ON")
            cursor.execute(
                "UPDATE transaction_transaction SET id = '10' WHERE id = %s",
                [self.exchange.pk.hex],
            )
            cursor.execute(
                "UPDATE review_rating_review SET transaction_id = '10' WHERE id = %s",
                [self.review.pk],
            )

        self.repair()
        converted_id = uuid.UUID(int=10)
        exchange = Transaction.objects.get(pk=converted_id)
        self.review.refresh_from_db()
        self.assertEqual(exchange.swap_request_id, self.exchange.swap_request_id)
        self.assertEqual(self.review.transaction_id, converted_id)
        self.assertEqual(self.review.comment, "Preserve this review.")
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(Review.objects.count(), 1)
        connection.check_constraints()

        self.repair()
        self.assertTrue(Transaction.objects.filter(pk=converted_id).exists())

    def test_leaves_valid_uuids_and_review_references_unchanged(self):
        original_id = self.exchange.pk
        self.repair()
        self.exchange.refresh_from_db()
        self.review.refresh_from_db()
        self.assertEqual(self.exchange.pk, original_id)
        self.assertEqual(self.review.transaction_id, self.exchange.pk)
