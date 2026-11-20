from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.transaction.models import Transaction

from .models import Review
from .tests import ReviewTestData


class ReviewAPITest(ReviewTestData, APITestCase):
    def setUp(self):
        self.api_url = reverse(
            "review_rating_api:review-create", args=[self.exchange.pk]
        )

    def test_participant_can_create_review(self):
        self.client.force_authenticate(user=self.requester)
        response = self.client.post(
            self.api_url, {"rating": 5, "comment": "Pertukaran lancar."}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author"], self.requester.username)
        self.assertEqual(response.data["recipient"], self.owner.username)
        self.assertEqual(Review.objects.count(), 1)

    def test_invalid_rating_is_rejected(self):
        self.client.force_authenticate(user=self.requester)
        response = self.client.post(self.api_url, {"rating": 6}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rating", response.data)
        self.assertFalse(Review.objects.exists())

    def test_cannot_review_same_transaction_twice(self):
        self.client.force_authenticate(user=self.requester)
        first = self.client.post(self.api_url, {"rating": 5}, format="json")
        second = self.client.post(self.api_url, {"rating": 4}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 1)

    def test_outsider_cannot_create_review(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.post(self.api_url, {"rating": 5}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Review.objects.exists())

    def test_unfinished_transaction_cannot_be_reviewed(self):
        self.exchange.status = Transaction.Status.WAITING
        self.exchange.save(update_fields=["status"])
        self.client.force_authenticate(user=self.requester)
        response = self.client.post(self.api_url, {"rating": 5}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Review.objects.exists())

    def test_public_reviews_hide_transaction_and_inactive_profiles(self):
        self.submit()
        url = reverse("review_rating_api:user-review-list", args=[self.owner.username])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertNotIn("transaction", response.data[0])
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_transaction_reviews_require_participation(self):
        self.submit()
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(self.client.get(self.api_url).status_code, 403)
        self.assertEqual(
            self.client.post(self.api_url, {"rating": 9}, format="json").status_code,
            403,
        )
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.api_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(str(response.data[0]["transaction"]), str(self.exchange.pk))

    def test_anonymous_user_cannot_submit(self):
        self.assertEqual(
            self.client.post(self.api_url, {"rating": 5}, format="json").status_code,
            403,
        )
