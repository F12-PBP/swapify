from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatRoom
from apps.clothing_catalog.models import Clothing
from apps.transaction.models import Transaction

from .models import SwapRequest
from .tests import make_clothing


class SwapRequestAPITestCase(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.requester = user_model.objects.create_user("alice", password="pass12345")
        self.owner = user_model.objects.create_user("bob", password="pass12345")
        self.stranger = user_model.objects.create_user("carol", password="pass12345")
        self.offered = make_clothing(self.requester, "Kemeja Alice")
        self.requested = make_clothing(self.owner, "Jaket Bob")
        self.swap = SwapRequest.objects.create(
            requester=self.requester,
            requested_clothing=self.requested,
            offered_clothing=self.offered,
        )

    def url(self, name, *args):
        return reverse(f"swap_request_api:swap-request-{name}", args=args)

    def post_action(self, user, action):
        self.client.force_authenticate(user=user)
        response = self.client.post(self.url(action, self.swap.pk))
        self.swap.refresh_from_db()
        return response


class SwapRequestListAPITests(SwapRequestAPITestCase):
    def test_list_requires_authentication(self):
        response = self.client.get(self.url("list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_shows_requests_for_both_participants(self):
        for user, role, actions in (
            (self.requester, "sent", ["cancel"]),
            (self.owner, "received", ["accept", "reject"]),
        ):
            self.client.force_authenticate(user=user)
            response = self.client.get(self.url("list"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["count"], 1)
            result = response.data["results"][0]
            self.assertEqual(result["id"], self.swap.pk)
            self.assertEqual(result["role"], role)
            self.assertEqual(result["actions"], actions)
            self.assertEqual(
                result["requested_clothing"]["uuid"], str(self.requested.uuid)
            )

    def test_list_hides_other_users_requests(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(self.url("list"))
        self.assertEqual(response.data["count"], 0)

    def test_list_filters_by_role_status_and_search(self):
        self.client.force_authenticate(user=self.owner)
        cases = (
            ({"role": "received"}, 1),
            ({"role": "sent"}, 0),
            ({"status": "pending"}, 1),
            ({"status": "accepted"}, 0),
            ({"search": "jaket"}, 1),
            ({"search": "tidak-ada"}, 0),
            ({"role": "invalid"}, 1),
        )
        for params, expected in cases:
            with self.subTest(params=params):
                response = self.client.get(self.url("list"), params)
                self.assertEqual(response.data["count"], expected)


class SwapRequestDetailAPITests(SwapRequestAPITestCase):
    def test_participant_can_read_detail(self):
        self.client.force_authenticate(user=self.requester)
        response = self.client.get(self.url("detail", self.swap.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["requester"], "alice")
        self.assertEqual(response.data["owner"], "bob")
        self.assertIsNone(response.data["transaction"])
        self.assertIsNone(response.data["chat_room"])
        self.assertFalse(response.data["has_reviewed"])

    def test_outsider_gets_not_found(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(self.url("detail", self.swap.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SwapRequestCreateAPITests(SwapRequestAPITestCase):
    def setUp(self):
        super().setUp()
        self.swap.delete()

    def create(self, user=None, **overrides):
        self.client.force_authenticate(user=user or self.requester)
        payload = {
            "requested_clothing": str(self.requested.uuid),
            "offered_clothing": str(self.offered.uuid),
            "message": "Mau tukar?",
            **overrides,
        }
        return self.client.post(self.url("list"), payload, format="json")

    def test_requester_can_create_swap_request(self):
        response = self.create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], SwapRequest.Status.PENDING)
        self.assertEqual(response.data["role"], "sent")
        self.assertEqual(response.data["message"], "Mau tukar?")
        self.assertEqual(SwapRequest.objects.count(), 1)

    def test_create_requires_authentication(self):
        response = self.client.post(self.url("list"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_clothing_is_rejected(self):
        response = self.create(
            requested_clothing="00000000-0000-0000-0000-000000000000"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("requested_clothing", response.data)
        self.assertFalse(SwapRequest.objects.exists())

    def test_same_clothing_is_rejected(self):
        response = self.create(offered_clothing=str(self.requested.uuid))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("offered_clothing", response.data)

    def test_cannot_offer_someone_elses_clothing(self):
        response = self.create(user=self.stranger)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SwapRequest.objects.exists())

    def test_unavailable_clothing_is_rejected(self):
        self.requested.status = Clothing.Status.RESERVED
        self.requested.save(update_fields=["status"])
        response = self.create()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(SwapRequest.objects.exists())

    def test_duplicate_pending_request_is_rejected(self):
        self.assertEqual(self.create().status_code, status.HTTP_201_CREATED)
        response = self.create()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SwapRequest.objects.count(), 1)


class SwapRequestActionAPITests(SwapRequestAPITestCase):
    def test_owner_can_accept(self):
        response = self.post_action(self.owner, "accept")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.swap.status, SwapRequest.Status.ACCEPTED)
        self.assertEqual(response.data["swap_request"]["actions"], [])
        self.assertTrue(ChatRoom.objects.filter(swap_request=self.swap).exists())
        transaction = Transaction.objects.get(swap_request=self.swap)
        self.assertEqual(
            response.data["swap_request"]["transaction"], str(transaction.pk)
        )
        self.requested.refresh_from_db()
        self.assertEqual(self.requested.status, Clothing.Status.RESERVED)

    def test_owner_can_reject(self):
        response = self.post_action(self.owner, "reject")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.swap.status, SwapRequest.Status.REJECTED)

    def test_requester_can_cancel(self):
        response = self.post_action(self.requester, "cancel")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.swap.status, SwapRequest.Status.CANCELLED)

    def test_wrong_role_gets_not_found(self):
        for user, action in (
            (self.requester, "accept"),
            (self.requester, "reject"),
            (self.owner, "cancel"),
            (self.stranger, "accept"),
        ):
            with self.subTest(user=user.username, action=action):
                response = self.post_action(user, action)
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(self.swap.status, SwapRequest.Status.PENDING)

    def test_finished_request_returns_conflict(self):
        self.post_action(self.owner, "reject")
        response = self.post_action(self.requester, "cancel")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already rejected", response.data["detail"])
        self.assertEqual(self.swap.status, SwapRequest.Status.REJECTED)

    def test_accept_with_reserved_clothing_returns_conflict(self):
        self.offered.status = Clothing.Status.RESERVED
        self.offered.save(update_fields=["status"])
        response = self.post_action(self.owner, "accept")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn(self.offered.name, response.data["detail"])
        self.assertEqual(self.swap.status, SwapRequest.Status.PENDING)
        self.assertFalse(Transaction.objects.filter(swap_request=self.swap).exists())

    def test_actions_require_authentication(self):
        response = self.client.post(self.url("accept", self.swap.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
