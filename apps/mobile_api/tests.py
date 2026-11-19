from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.chat.models import ChatRoom
from apps.clothing_catalog.models import Clothing
from apps.review_rating.models import Review
from apps.swap_request.models import SwapRequest
from apps.transaction.models import Transaction

User = get_user_model()


class MobileApiTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="Correct-Horse-42!"
        )
        self.bob = User.objects.create_user(
            username="bob", password="Correct-Horse-42!"
        )
        self.eve = User.objects.create_user(
            username="eve", password="Correct-Horse-42!"
        )
        self.alice_item = self.make_clothing(self.alice, "Alice shirt")
        self.bob_item = self.make_clothing(self.bob, "Bob jacket")
        self.swap = SwapRequest.objects.create(
            requester=self.alice,
            requested_clothing=self.bob_item,
            offered_clothing=self.alice_item,
            status=SwapRequest.Status.ACCEPTED,
        )
        self.exchange = Transaction.objects.create(
            swap_request=self.swap,
            status=Transaction.Status.COMPLETED,
            meetup_date=timezone.now(),
            meetup_location="Campus",
            requester_received=True,
            owner_received=True,
            completed_at=timezone.now(),
        )
        self.room, _ = ChatRoom.objects.get_or_create(swap_request=self.swap)
        Review.objects.create(
            transaction=self.exchange,
            author=self.alice,
            recipient=self.bob,
            rating=5,
            comment="Great swap",
        )

    @staticmethod
    def make_clothing(owner, name, status=Clothing.Status.AVAILABLE):
        return Clothing.objects.create(
            owner=owner,
            name=name,
            description="Good condition",
            type=Clothing.Type.TOP,
            size=Clothing.Size.M,
            condition=Clothing.Condition.GOOD,
            status=status,
        )

    def test_token_login_and_profile_update_are_scoped_to_authenticated_user(self):
        login_url = reverse("mobile_api:token")
        response = self.client.post(
            login_url,
            {"username": "alice", "password": "Correct-Horse-42!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        profile_url = reverse("mobile_api:profile")
        response = self.client.get(profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "alice")
        self.assertIsNone(response.data["profile_picture_url"])

        response = self.client.patch(
            profile_url, {"display_name": "Alice A."}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.display_name, "Alice A.")
        self.assertEqual(self.bob.profile.display_name, "bob")

        self.client.post(reverse("mobile_api:logout"), format="json")
        self.assertFalse(Token.objects.filter(user=self.alice).exists())

    def test_profile_location_and_style_preferences_are_validated(self):
        self.client.force_authenticate(self.alice)
        profile_url = reverse("mobile_api:profile")
        for data in (
            {"preferences": ["tops", "not-a-style"]},
            {"latitude": 91, "longitude": 0},
            {"latitude": 0},
        ):
            with self.subTest(data=data):
                self.assertEqual(
                    self.client.patch(profile_url, data, format="json").status_code,
                    400,
                )

    def test_api_requires_authentication_and_hides_unavailable_catalog_items(self):
        for route in (
            "mobile_api:profile",
            "mobile_api:catalog-list",
            "mobile_api:swap-request-list",
            "mobile_api:transaction-list",
            "mobile_api:chat-list",
            "mobile_api:review-list",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 401)

        self.client.force_authenticate(self.alice)
        reserved = self.make_clothing(self.bob, "Reserved", Clothing.Status.RESERVED)
        my_reserved = self.make_clothing(
            self.alice, "My reserved", Clothing.Status.RESERVED
        )
        response = self.client.get(reverse("mobile_api:catalog-list"))
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(self.alice_item.pk, ids)
        self.assertIn(self.bob_item.pk, ids)
        self.assertIn(my_reserved.pk, ids)
        self.assertNotIn(reserved.pk, ids)
        self.assertEqual(
            self.client.get(
                reverse("mobile_api:catalog-detail", kwargs={"pk": reserved.pk})
            ).status_code,
            404,
        )

    def test_lists_are_user_scoped_and_chat_messages_require_room_membership(self):
        self.client.force_authenticate(self.alice)
        for route in (
            "mobile_api:swap-request-list",
            "mobile_api:transaction-list",
            "mobile_api:chat-list",
            "mobile_api:review-list",
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 1)

        messages_url = reverse("mobile_api:chat-messages", kwargs={"pk": self.room.pk})
        response = self.client.post(
            messages_url, {"message": "  Ready to swap?  "}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Ready to swap?")

        self.client.force_authenticate(self.eve)
        self.assertEqual(self.client.get(messages_url).status_code, 404)
