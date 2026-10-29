from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clothing_catalog.models import Clothing
from apps.swap_request.models import SwapRequest
from apps.swap_request.services import accept_swap_request

from .models import Transaction
from .services import confirm_receipt, start_transaction


class TransactionPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.requester = user_model.objects.create_user(username="requester")
        cls.owner = user_model.objects.create_user(username="owner")
        cls.outsider = user_model.objects.create_user(username="outsider")
        items = []
        for user in (cls.requester, cls.owner):
            items.append(
                Clothing.objects.create(
                    owner=user,
                    name=f"{user.username}'s shirt",
                    description="Test clothing",
                    type=Clothing.Type.TOP,
                    size=Clothing.Size.M,
                    condition=Clothing.Condition.GOOD,
                )
            )
        swap = SwapRequest.objects.create(
            requester=cls.requester,
            offered_clothing=items[0],
            requested_clothing=items[1],
        )
        accept_swap_request(swap.pk, cls.owner)
        cls.exchange = Transaction.objects.get(swap_request=swap)

    def url(self, action):
        return reverse(f"transaction_{action}", args=[self.exchange.pk])

    def start_meetup(self):
        self.exchange.meetup_date = timezone.now() + timedelta(days=1)
        self.exchange.meetup_location = "Campus entrance"
        self.exchange.save(update_fields=["meetup_date", "meetup_location"])
        self.exchange = start_transaction(self.exchange.pk, self.owner)

    def test_anonymous_users_cannot_view_edit_or_confirm(self):
        for method, action in (
            ("get", "detail"),
            ("get", "update"),
            ("post", "update"),
            ("post", "received"),
            ("post", "start"),
        ):
            with self.subTest(method=method, action=action):
                response = getattr(self.client, method)(self.url(action))
                self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertFalse(self.exchange.requester_received)
        self.assertFalse(self.exchange.owner_received)

    def test_outsiders_cannot_view_edit_or_confirm(self):
        self.client.force_login(self.outsider)
        for method, action in (
            ("get", "detail"),
            ("get", "update"),
            ("post", "update"),
            ("post", "received"),
            ("post", "start"),
        ):
            with self.subTest(method=method, action=action):
                response = getattr(self.client, method)(self.url(action))
                self.assertEqual(response.status_code, 404)
        self.exchange.refresh_from_db()
        self.assertFalse(self.exchange.requester_received)
        self.assertFalse(self.exchange.owner_received)

    def test_participants_can_view_detail_and_update(self):
        for user in (self.requester, self.owner):
            self.client.force_login(user)
            for action in ("detail", "update"):
                with self.subTest(user=user.username, action=action):
                    self.assertEqual(self.client.get(self.url(action)).status_code, 200)

    def test_delivery_form_only_displays_current_partys_fields(self):
        self.exchange.method = Transaction.Method.DELIVERY
        self.exchange.save(update_fields=["method"])
        for user, own, other in (
            (self.requester, "requester_resi", "owner_resi"),
            (self.owner, "owner_resi", "requester_resi"),
        ):
            self.client.force_login(user)
            with self.subTest(user=user.username):
                response = self.client.get(self.url("update"))
                self.assertContains(response, f'name="{own}"')
                self.assertNotContains(response, f'name="{other}"')

    def test_delivery_updates_ignore_other_partys_submitted_fields(self):
        for user, own, other in (
            (self.requester, "requester_resi", "owner_resi"),
            (self.owner, "owner_resi", "requester_resi"),
        ):
            with self.subTest(user=user.username):
                Transaction.objects.filter(pk=self.exchange.pk).update(
                    method=Transaction.Method.DELIVERY,
                    requester_resi="original-requester",
                    owner_resi="original-owner",
                )
                self.client.force_login(user)
                response = self.client.post(
                    self.url("update"),
                    {
                        "method": Transaction.Method.DELIVERY,
                        own: "my-new-tracking",
                        other: "tampered-tracking",
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.exchange.refresh_from_db()
                self.assertEqual(getattr(self.exchange, own), "my-new-tracking")
                self.assertEqual(
                    getattr(self.exchange, other),
                    "original-owner" if other == "owner_resi" else "original-requester",
                )

    def test_receipt_uses_current_user_even_when_party_is_forged(self):
        self.start_meetup()
        for user, own, other, forged_party in (
            (self.requester, "requester_received", "owner_received", "owner"),
            (self.owner, "owner_received", "requester_received", "requester"),
        ):
            with self.subTest(user=user.username):
                Transaction.objects.filter(pk=self.exchange.pk).update(
                    requester_received=False, owner_received=False
                )
                self.client.force_login(user)
                response = self.client.post(
                    self.url("received"), {"party": forged_party}
                )
                self.assertEqual(response.status_code, 302)
                self.exchange.refresh_from_db()
                self.assertTrue(getattr(self.exchange, own))
                self.assertFalse(getattr(self.exchange, other))

    def test_both_participants_can_confirm_without_overwriting_each_other(self):
        self.start_meetup()
        for user in (self.requester, self.owner):
            self.client.force_login(user)
            response = self.client.post(self.url("received"))
            self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertTrue(self.exchange.requester_received)
        self.assertTrue(self.exchange.owner_received)
        self.assertEqual(self.exchange.status, Transaction.Status.COMPLETED)

    def test_receipt_requires_post(self):
        self.client.force_login(self.requester)
        self.assertEqual(self.client.get(self.url("received")).status_code, 405)

    def test_standalone_create_and_delete_routes_are_unavailable(self):
        self.client.force_login(self.owner)
        for path in (
            "/transaction/create/",
            f"/transaction/{self.exchange.pk}/delete/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 404)
        self.assertTrue(Transaction.objects.filter(pk=self.exchange.pk).exists())

    def test_waiting_transaction_can_be_validated_without_meetup_details(self):
        self.exchange.full_clean()

    def test_method_can_be_selected_and_incomplete_draft_saved(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            self.url("update"), {"method": Transaction.Method.DELIVERY}
        )
        self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.method, Transaction.Method.DELIVERY)
        self.assertEqual(self.exchange.status, Transaction.Status.WAITING)

    def test_start_rejects_missing_meetup_details_with_visible_errors(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url("start"), follow=True)
        self.assertContains(response, "Meetup date is required")
        self.assertContains(response, "Meetup location is required")
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.WAITING)

    def test_either_participant_can_start_a_ready_meetup(self):
        self.exchange.meetup_date = timezone.now() + timedelta(days=1)
        self.exchange.meetup_location = "Campus"
        self.exchange.save()
        for user in (self.owner, self.requester):
            Transaction.objects.filter(pk=self.exchange.pk).update(
                status=Transaction.Status.WAITING
            )
            self.client.force_login(user)
            response = self.client.post(self.url("start"))
            self.assertEqual(response.status_code, 302)
            self.exchange.refresh_from_db()
            self.assertEqual(self.exchange.status, Transaction.Status.IN_PROGRESS)

    def test_delivery_requires_details_from_both_participants(self):
        self.exchange.method = Transaction.Method.DELIVERY
        self.exchange.requester_resi = "REQUESTER123"
        self.exchange.requester_delivery_estimate = timezone.now() + timedelta(days=2)
        self.exchange.save()
        with self.assertRaises(ValidationError) as result:
            start_transaction(self.exchange.pk, self.requester)
        self.assertIn("owner_resi", result.exception.message_dict)
        self.assertIn("owner_delivery_estimate", result.exception.message_dict)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.WAITING)

    def test_delivery_can_be_filled_by_each_party_then_started(self):
        estimate = (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        for user, party in ((self.requester, "requester"), (self.owner, "owner")):
            self.client.force_login(user)
            response = self.client.post(
                self.url("update"),
                {
                    "method": Transaction.Method.DELIVERY,
                    f"{party}_resi": f"TRACK-{party}",
                    f"{party}_delivery_estimate": estimate,
                },
            )
            self.assertEqual(response.status_code, 302)
        self.client.post(self.url("start"))
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.IN_PROGRESS)
        confirm_receipt(self.exchange.pk, self.owner)
        exchange = confirm_receipt(self.exchange.pk, self.requester)
        self.assertEqual(exchange.status, Transaction.Status.COMPLETED)

    def test_receipt_before_start_is_rejected(self):
        self.client.force_login(self.requester)
        response = self.client.post(self.url("received"), follow=True)
        self.assertContains(response, "Start the exchange before confirming receipt")
        self.exchange.refresh_from_db()
        self.assertFalse(self.exchange.requester_received)
        self.assertIsNone(self.exchange.requester_received_at)

    def test_first_receipt_records_time_but_keeps_items_reserved(self):
        self.start_meetup()
        exchange = confirm_receipt(self.exchange.pk, self.owner)
        self.assertTrue(exchange.owner_received)
        self.assertIsNotNone(exchange.owner_received_at)
        self.assertFalse(exchange.requester_received)
        self.assertIsNone(exchange.requester_received_at)
        self.assertEqual(exchange.status, Transaction.Status.IN_PROGRESS)
        self.assertIsNone(exchange.completed_at)
        self.assertEqual(
            Clothing.objects.filter(status=Clothing.Status.RESERVED).count(), 2
        )

    def test_second_receipt_completes_and_swaps_both_items(self):
        self.start_meetup()
        confirm_receipt(self.exchange.pk, self.owner)
        exchange = confirm_receipt(self.exchange.pk, self.requester)
        self.assertEqual(exchange.status, Transaction.Status.COMPLETED)
        self.assertIsNotNone(exchange.requester_received_at)
        self.assertIsNotNone(exchange.owner_received_at)
        self.assertIsNotNone(exchange.completed_at)
        self.assertEqual(
            Clothing.objects.filter(status=Clothing.Status.SWAPPED).count(), 2
        )

    def test_repeated_receipts_preserve_timestamps(self):
        self.start_meetup()
        first = confirm_receipt(self.exchange.pk, self.requester)
        receipt_time = first.requester_received_at
        later = timezone.now() + timedelta(hours=1)
        with patch("apps.transaction.services.timezone.now", return_value=later):
            again = confirm_receipt(self.exchange.pk, self.requester)
        self.assertEqual(again.requester_received_at, receipt_time)
        completed = confirm_receipt(self.exchange.pk, self.owner)
        completed_at = completed.completed_at
        with patch("apps.transaction.services.timezone.now", return_value=later):
            again = confirm_receipt(self.exchange.pk, self.owner)
        self.assertEqual(again.completed_at, completed_at)
        self.assertEqual(again.requester_received_at, receipt_time)

    def test_completion_failure_rolls_back_clothing_and_second_receipt(self):
        self.start_meetup()
        confirm_receipt(self.exchange.pk, self.owner)
        with patch(
            "apps.transaction.services.Transaction.save",
            side_effect=RuntimeError("Database write failed"),
        ):
            with self.assertRaises(RuntimeError):
                confirm_receipt(self.exchange.pk, self.requester)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.IN_PROGRESS)
        self.assertTrue(self.exchange.owner_received)
        self.assertFalse(self.exchange.requester_received)
        self.assertIsNone(self.exchange.requester_received_at)
        self.assertIsNone(self.exchange.completed_at)
        self.assertEqual(
            Clothing.objects.filter(status=Clothing.Status.RESERVED).count(), 2
        )

    def test_details_are_locked_after_start_and_completion(self):
        self.start_meetup()
        for status in (Transaction.Status.IN_PROGRESS, Transaction.Status.COMPLETED):
            if status == Transaction.Status.COMPLETED:
                confirm_receipt(self.exchange.pk, self.requester)
                confirm_receipt(self.exchange.pk, self.owner)
            for user in (self.requester, self.owner):
                self.client.force_login(user)
                with self.subTest(status=status, user=user.username):
                    self.assertEqual(
                        self.client.get(self.url("update")).status_code, 403
                    )
                    response = self.client.post(
                        self.url("update"),
                        {"method": "Delivery", "meetup_location": "Changed"},
                    )
                    self.assertEqual(response.status_code, 403)
            self.exchange.refresh_from_db()
            self.assertEqual(self.exchange.meetup_location, "Campus entrance")
            self.assertEqual(self.exchange.method, Transaction.Method.MEETUP)

    def test_closed_transactions_reject_start_and_receipt(self):
        for status in (Transaction.Status.CANCELLED, Transaction.Status.DISPUTED):
            Transaction.objects.filter(pk=self.exchange.pk).update(status=status)
            for operation in (start_transaction, confirm_receipt):
                with self.subTest(status=status, operation=operation.__name__):
                    with self.assertRaises(ValidationError):
                        operation(self.exchange.pk, self.owner)
            self.exchange.refresh_from_db()
            self.assertFalse(self.exchange.owner_received)

    def test_services_deny_outsiders_even_without_a_view(self):
        for operation in (start_transaction, confirm_receipt):
            with self.assertRaises(PermissionDenied):
                operation(self.exchange.pk, self.outsider)

    def test_start_is_post_only_and_repeated_start_is_safe(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url("start")).status_code, 405)
        self.start_meetup()
        self.client.post(self.url("start"))
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.IN_PROGRESS)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_detail_actions_follow_the_lifecycle(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url("detail"))
        self.assertContains(response, self.url("start"))
        self.assertNotContains(response, self.url("received"))
        self.start_meetup()
        response = self.client.get(self.url("detail"))
        self.assertContains(response, self.url("received"))
        self.assertNotContains(response, self.url("update"))
        confirm_receipt(self.exchange.pk, self.owner)
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "Your receipt is confirmed")
        self.assertNotContains(response, self.url("received"))
        confirm_receipt(self.exchange.pk, self.requester)
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "This exchange is complete")
        self.assertNotContains(response, self.url("received"))
