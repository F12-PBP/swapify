from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase


class ProfileAPITest(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alfi", password="test-password-123"
        )
        self.my_profile_url = reverse("user_profile_api:my-profile")
        self.public_profile_url = reverse(
            "user_profile_api:public-profile", args=["alfi"]
        )

    def test_public_profile_can_be_read(self):
        response = self.client.get(self.public_profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "alfi")
        self.assertNotIn("latitude", response.data)
        self.assertNotIn("longitude", response.data)

    def test_my_profile_requires_login(self):
        response = self.client.get(self.my_profile_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_update_own_profile(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.my_profile_url,
            {"display_name": "Alfi", "preferences": ["tops", "outerwear"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.display_name, "Alfi")
        self.assertEqual(self.user.profile.preferences, ["tops", "outerwear"])

    def test_invalid_preference_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.my_profile_url, {"preferences": ["not-a-real-style"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("preferences", response.data)

    def test_location_and_onboarding_cannot_be_changed(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.my_profile_url,
            {"city": "Fake city", "onboarding_completed": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertNotEqual(self.user.profile.city, "Fake city")
        self.assertFalse(self.user.profile.onboarding_completed)

    def test_login_without_csrf_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            reverse("user_profile_api:login"),
            {"username": "alfi", "password": "test-password-123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_and_write_with_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get(reverse("user_profile_api:csrf"))
        csrf_token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("user_profile_api:login"),
            {"username": "alfi", "password": "test-password-123"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csrf_token = client.cookies["csrftoken"].value
        response = client.patch(
            self.my_profile_url,
            {"bio": "Hello from the API."},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
