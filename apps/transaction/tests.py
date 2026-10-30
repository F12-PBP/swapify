from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clothing_catalog.models import Clothing
from apps.swap_request.models import SwapRequest
from apps.swap_request.services import accept_swap_request

from .forms import UpdateTransactionForm
from .models import Transaction
from .services import confirm_receipt, start_transaction, validate_resi


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
        start_transaction(self.exchange.pk, self.requester)
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
                        f"{own.removesuffix('_resi')}_courier": "JNE",
                        f"{own.removesuffix('_resi')}_delivery_estimate": (
                            timezone.now() + timedelta(days=2)
                        ).isoformat(),
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

    def test_delivery_method_requires_own_details_before_saving(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            self.url("update"), {"method": Transaction.Method.DELIVERY}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("requester_resi", response.context["form"].errors)
        self.assertIn("requester_delivery_estimate", response.context["form"].errors)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.method, Transaction.Method.MEETUP)
        self.assertEqual(self.exchange.status, Transaction.Status.WAITING)

    def test_incomplete_meetup_draft_can_be_saved_before_readiness(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            self.url("update"), {"method": Transaction.Method.MEETUP}
        )
        self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.WAITING)
        self.assertIsNone(self.exchange.meetup_date)

    def test_start_rejects_missing_meetup_details_with_visible_errors(self):
        start_transaction(self.exchange.pk, self.requester)
        self.client.force_login(self.owner)
        response = self.client.post(self.url("start"), follow=True)
        self.assertContains(response, "Meetup date is required")
        self.assertContains(response, "Meetup location is required")
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.WAITING)

    def test_meetup_starts_only_after_both_participants_are_ready(self):
        self.exchange.meetup_date = timezone.now() + timedelta(days=1)
        self.exchange.meetup_location = "Campus"
        self.exchange.save()
        for first, second in (
            (self.owner, self.requester),
            (self.requester, self.owner),
        ):
            with self.subTest(first=first.username):
                Transaction.objects.filter(pk=self.exchange.pk).update(
                    status=Transaction.Status.WAITING,
                    requester_started=False,
                    owner_started=False,
                )
                self.client.force_login(first)
                response = self.client.post(self.url("start"), follow=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response, "You are ready. Waiting for the other party"
                )
                self.exchange.refresh_from_db()
                self.assertEqual(self.exchange.status, Transaction.Status.WAITING)
                self.client.force_login(second)
                response = self.client.post(self.url("start"), follow=True)
                self.assertContains(
                    response, "Exchange started. Details are now locked."
                )
                self.exchange.refresh_from_db()
                self.assertEqual(self.exchange.status, Transaction.Status.IN_PROGRESS)

    def test_delivery_requires_details_from_both_participants(self):
        self.exchange.method = Transaction.Method.DELIVERY
        self.exchange.requester_resi = "REQUESTER123"
        self.exchange.requester_delivery_estimate = timezone.now() + timedelta(days=2)
        self.exchange.save()
        with self.assertRaisesMessage(
            ValidationError, "Both tracking numbers must be validated"
        ):
            start_transaction(self.exchange.pk, self.requester)
        self.exchange.status = Transaction.Status.IN_PROGRESS
        with self.assertRaises(ValidationError) as result:
            self.exchange.full_clean()
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
                    f"{party}_courier": "JNE",
                    f"{party}_delivery_estimate": estimate,
                },
            )
            self.assertEqual(response.status_code, 302)
        for user in (self.requester, self.owner):
            self.client.force_login(user)
            self.assertEqual(
                self.client.post(
                    reverse("validate_resi", args=[self.exchange.pk])
                ).status_code,
                302,
            )
        for user in (self.requester, self.owner):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url("start")).status_code, 302)
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
        self.assertContains(response, "Your item has been confirmed")
        self.assertNotContains(response, self.url("received"))
        confirm_receipt(self.exchange.pk, self.requester)
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "Swapping is complete!")
        self.assertNotContains(response, self.url("received"))


class TransactionLifecycleGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.requester = User.objects.create_user(username="guard-requester")
        cls.owner = User.objects.create_user(username="guard-owner")
        for user, name in [
            (cls.requester, "Requester Display"),
            (cls.owner, "Owner Display"),
        ]:
            user.profile.display_name = name
            user.profile.save(update_fields=["display_name"])
        cls.offered = Clothing.objects.create(
            owner=cls.requester,
            name="Requester linen shirt",
            type="top",
            size="M",
            condition="good",
        )
        cls.requested = Clothing.objects.create(
            owner=cls.owner,
            name="Owner denim jacket",
            type="outerwear",
            size="M",
            condition="good",
        )
        cls.swap = SwapRequest.objects.create(
            requester=cls.requester,
            offered_clothing=cls.offered,
            requested_clothing=cls.requested,
        )
        accept_swap_request(cls.swap.pk, cls.owner)
        cls.exchange = Transaction.objects.get(swap_request=cls.swap)
        cls.arrival = (timezone.now() + timedelta(days=3)).replace(
            second=0, microsecond=0
        )

    def delivery(self):
        self.exchange.method = Transaction.Method.DELIVERY
        self.exchange.requester_courier = "Requester courier"
        self.exchange.requester_resi = "REQUESTER-001"
        self.exchange.requester_delivery_estimate = self.arrival
        self.exchange.owner_courier = "Owner courier"
        self.exchange.owner_resi = "OWNER-001"
        self.exchange.owner_delivery_estimate = self.arrival
        self.exchange.save()

    def delivery_payload(self, party="requester", **changes):
        return {
            "method": "Delivery",
            f"{party}_courier": getattr(self.exchange, f"{party}_courier"),
            f"{party}_resi": getattr(self.exchange, f"{party}_resi"),
            f"{party}_delivery_estimate": self.arrival.isoformat(),
            **changes,
        }

    def validate_both(self):
        validate_resi(self.exchange.pk, self.owner)
        validate_resi(self.exchange.pk, self.requester)
        self.exchange.refresh_from_db()

    def test_empty_partner_tracking_number_cannot_be_validated(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                Transaction.objects.filter(pk=self.exchange.pk).update(owner_resi=value)
                with self.assertRaisesMessage(
                    ValidationError, "has not added a tracking number"
                ):
                    validate_resi(self.exchange.pk, self.requester)
                self.exchange.refresh_from_db()
                self.assertFalse(self.exchange.owner_resi_valid)

    def test_delivery_waits_for_both_validations_and_both_ready_flags(self):
        self.delivery()
        with self.assertRaisesMessage(
            ValidationError, "Both tracking numbers must be validated"
        ):
            start_transaction(self.exchange.pk, self.requester)
        validate_resi(self.exchange.pk, self.owner)
        with self.assertRaises(ValidationError):
            start_transaction(self.exchange.pk, self.owner)
        validate_resi(self.exchange.pk, self.requester)
        exchange = start_transaction(self.exchange.pk, self.owner)
        self.assertEqual(exchange.status, Transaction.Status.WAITING)
        exchange = start_transaction(self.exchange.pk, self.requester)
        self.assertEqual(exchange.status, Transaction.Status.IN_PROGRESS)
        confirm_receipt(exchange.pk, self.requester)
        confirm_receipt(exchange.pk, self.owner)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.COMPLETED)

    def test_changed_delivery_details_reset_readiness_and_own_validation(self):
        self.delivery()
        self.validate_both()
        start_transaction(self.exchange.pk, self.owner)
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("transaction_update", args=[self.exchange.pk]),
            self.delivery_payload(requester_resi="REQUESTER-002"),
        )
        self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertFalse(self.exchange.owner_started)
        self.assertFalse(self.exchange.requester_started)
        self.assertFalse(self.exchange.requester_resi_valid)
        self.assertTrue(self.exchange.owner_resi_valid)
        with self.assertRaises(ValidationError):
            start_transaction(self.exchange.pk, self.requester)

    def test_owner_edit_invalidates_only_the_owners_tracking_confirmation(self):
        self.delivery()
        self.validate_both()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("transaction_update", args=[self.exchange.pk]),
            self.delivery_payload("owner", owner_courier="New owner courier"),
        )
        self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertTrue(self.exchange.requester_resi_valid)
        self.assertFalse(self.exchange.owner_resi_valid)

    def test_delivery_post_requires_an_arrival_estimate(self):
        self.delivery()
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("transaction_update", args=[self.exchange.pk]),
            self.delivery_payload(requester_delivery_estimate=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estimated arrival is required for delivery.")

    def test_method_change_resets_both_validations(self):
        self.delivery()
        self.validate_both()
        start_transaction(self.exchange.pk, self.owner)
        self.exchange.refresh_from_db()
        form = UpdateTransactionForm(
            {
                "method": "Meetup",
                "meetup_location": "Community library",
                "meetup_date": self.arrival.isoformat(),
            },
            instance=self.exchange,
            user=self.requester,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.exchange.refresh_from_db()
        self.assertFalse(self.exchange.requester_resi_valid)
        self.assertFalse(self.exchange.owner_resi_valid)
        self.assertFalse(self.exchange.owner_started)

    def test_unchanged_submission_keeps_readiness_and_validation(self):
        self.delivery()
        self.validate_both()
        start_transaction(self.exchange.pk, self.owner)
        self.exchange.refresh_from_db()
        form = UpdateTransactionForm(
            self.delivery_payload(),
            instance=self.exchange,
            user=self.requester,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.has_changed(), form.changed_data)
        form.save()
        self.exchange.refresh_from_db()
        self.assertTrue(self.exchange.owner_started)
        self.assertTrue(self.exchange.requester_resi_valid)
        self.assertTrue(self.exchange.owner_resi_valid)

    def test_unchanged_delivery_post_preserves_readiness_and_validation(self):
        self.delivery()
        self.validate_both()
        start_transaction(self.exchange.pk, self.owner)
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse("transaction_update", args=[self.exchange.pk]),
            self.delivery_payload(),
        )
        self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertTrue(self.exchange.owner_started)
        self.assertFalse(self.exchange.requester_started)
        self.assertTrue(self.exchange.requester_resi_valid)
        self.assertTrue(self.exchange.owner_resi_valid)

    def test_save_without_commit_resets_the_instance_but_does_not_write(self):
        self.delivery()
        self.validate_both()
        start_transaction(self.exchange.pk, self.owner)
        self.exchange.refresh_from_db()
        form = UpdateTransactionForm(
            self.delivery_payload(requester_courier="New courier"),
            instance=self.exchange,
            user=self.requester,
        )
        self.assertTrue(form.is_valid(), form.errors)
        draft = form.save(commit=False)
        self.assertFalse(draft.requester_resi_valid)
        self.assertFalse(draft.owner_started)
        saved = Transaction.objects.get(pk=draft.pk)
        self.assertTrue(saved.requester_resi_valid)
        self.assertTrue(saved.owner_started)

    def test_detail_shows_couriers_pieces_display_names_and_correct_receipt_colors(
        self,
    ):
        self.delivery()
        self.validate_both()
        start_transaction(self.exchange.pk, self.requester)
        start_transaction(self.exchange.pk, self.owner)
        self.client.force_login(self.requester)
        url = reverse("transaction_detail", args=[self.exchange.pk])
        response = self.client.get(url)
        for text in (
            "Requester courier",
            "Owner courier",
            "Requester linen shirt",
            "Owner denim jacket",
            "From Requester Display",
            "From Owner Display",
        ):
            self.assertContains(response, text)
        self.assertRegex(
            response.content.decode(),
            r'Requester Display:\s*<span class="font-bold text-red-70">\s*Not yet',
        )
        confirm_receipt(self.exchange.pk, self.requester)
        response = self.client.get(url)
        self.assertRegex(
            response.content.decode(),
            r'Requester Display:\s*<span class="font-bold text-green-80">\s*Received',
        )
        self.assertRegex(
            response.content.decode(),
            r'Owner Display:\s*<span class="font-bold text-red-70">\s*Not yet',
        )

    def test_detail_uses_one_shared_flash_message_component(self):
        self.client.force_login(self.requester)
        self.client.post(reverse("validate_resi", args=[self.exchange.pk]))
        response = self.client.get(
            reverse("transaction_detail", args=[self.exchange.pk])
        )
        self.assertContains(response, "data-toast-messages", count=1)
        self.assertNotContains(response, 'class="alert alert-error')

    def test_meetup_still_completes_without_tracking_validations(self):
        self.exchange.meetup_date = self.arrival
        self.exchange.meetup_location = "Community library"
        self.exchange.save(update_fields=["meetup_date", "meetup_location"])
        start_transaction(self.exchange.pk, self.requester)
        exchange = start_transaction(self.exchange.pk, self.owner)
        self.assertEqual(exchange.status, Transaction.Status.IN_PROGRESS)
        confirm_receipt(exchange.pk, self.requester)
        confirm_receipt(exchange.pk, self.owner)
        self.exchange.refresh_from_db()
        self.assertEqual(self.exchange.status, Transaction.Status.COMPLETED)

    def test_participant_queryset_preloads_profiles_and_both_pieces(self):
        from .views import TransactionDetailView

        request = RequestFactory().get("/")
        request.user = self.requester
        view = TransactionDetailView()
        view.setup(request)
        exchange = view.get_queryset().get(pk=self.exchange.pk)
        with self.assertNumQueries(0):
            self.assertEqual(
                exchange.requester.profile.display_name, "Requester Display"
            )
            self.assertEqual(exchange.owner.profile.display_name, "Owner Display")
            self.assertEqual(
                exchange.swap_request.offered_clothing.name, self.offered.name
            )
