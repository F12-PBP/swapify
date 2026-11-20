from unittest.mock import patch

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


class ProfileWorkflowAPITest(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="member", password="test-password-123"
        )
        self.client.force_authenticate(self.user)

    def test_register_creates_profile_and_session(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get(reverse("user_profile_api:csrf"))
        token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("user_profile_api:register"),
            {
                "username": "newmember",
                "name": "New Member",
                "password1": "strong-pass-458!",
                "password2": "strong-pass-458!",
                "community_agreement": True,
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            client.get(reverse("user_profile_api:my-profile")).data["display_name"],
            "New Member",
        )

    def test_register_requires_csrf_and_agreement(self):
        client = APIClient(enforce_csrf_checks=True)
        url = reverse("user_profile_api:register")
        self.assertEqual(client.post(url, {}, format="json").status_code, 403)
        client.get(reverse("user_profile_api:csrf"))
        token = client.cookies["csrftoken"].value
        response = client.post(
            url,
            {
                "username": "newmember",
                "name": "Member",
                "password1": "strong-pass-458!",
                "password2": "strong-pass-458!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("community_agreement", response.data)

    def test_manual_location_clears_old_coordinates(self):
        profile = self.user.profile
        profile.latitude, profile.longitude = -6.2, 106.8
        profile.save()
        response = self.client.put(
            reverse("user_profile_api:location"),
            {"city": "Depok", "province": "West Java"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertIsNone(profile.latitude)
        self.assertEqual(profile.city, "Depok")

    def test_onboarding_validates_steps_and_completes(self):
        def url(step):
            return reverse("user_profile_api:onboarding", args=[step])

        self.assertEqual(
            self.client.post(
                url(2), {"city": "Depok", "province": "West Java"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                url(1), {"display_name": "Member", "bio": "Hi"}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                url(2),
                {"city": "Depok", "province": "West Java", "location_agreement": True},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                url(3), {"preferences": ["tops"]}, format="json"
            ).status_code,
            200,
        )
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.onboarding_completed)
        self.assertEqual(self.user.profile.preferences, ["tops"])

    def test_photo_rejects_invalid_upload(self):
        response = self.client.post(
            reverse("user_profile_api:photo"), {}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_profile_picture", response.data)

    def test_inactive_profile_is_not_public(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.get(
            reverse("user_profile_api:public-profile", args=[self.user.username])
        )
        self.assertEqual(response.status_code, 404)

    @patch("apps.user_profile.api_views.reverse_geocode")
    def test_resolve_and_save_signed_location(self, lookup):
        lookup.return_value = {
            "district": "Beji",
            "city": "Depok",
            "province": "West Java",
            "latitude": -6.2,
            "longitude": 106.8,
        }
        response = self.client.post(
            reverse("user_profile_api:location-resolve"),
            {"latitude": -6.2, "longitude": 106.8},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        response = self.client.put(
            reverse("user_profile_api:location"), response.data, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.latitude, -6.2)

    @patch("apps.user_profile.api_views.upload_profile_picture")
    def test_photo_upload_uses_service(self, upload):
        from cloudinary import CloudinaryImage

        from apps.user_profile.tests import image_upload

        upload.return_value = CloudinaryImage("swapify/profile-pictures/photo")
        response = self.client.post(
            reverse("user_profile_api:photo"),
            {"new_profile_picture": image_upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertIn("photo", str(self.user.profile.profile_picture))
        upload.assert_called_once()
