from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.clothing_catalog.models import Clothing
from apps.swap_request.models import SwapRequest
from apps.swap_request.services import accept_swap_request

from .models import Transaction


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

    def test_anonymous_users_cannot_view_edit_or_confirm(self):
        for method, action in (
            ("get", "detail"),
            ("get", "update"),
            ("post", "update"),
            ("post", "received"),
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
                    {own: "my-new-tracking", other: "tampered-tracking"},
                )
                self.assertEqual(response.status_code, 302)
                self.exchange.refresh_from_db()
                self.assertEqual(getattr(self.exchange, own), "my-new-tracking")
                self.assertEqual(
                    getattr(self.exchange, other),
                    "original-owner" if other == "owner_resi" else "original-requester",
                )

    def test_receipt_uses_current_user_even_when_party_is_forged(self):
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
        for user in (self.requester, self.owner):
            self.client.force_login(user)
            response = self.client.post(self.url("received"))
            self.assertEqual(response.status_code, 302)
        self.exchange.refresh_from_db()
        self.assertTrue(self.exchange.requester_received)
        self.assertTrue(self.exchange.owner_received)

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
