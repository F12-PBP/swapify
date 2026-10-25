from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class ProfileLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="location_owner")
        cls.other = get_user_model().objects.create_user(username="location_other")
        cls.url = reverse("user_profile:location_edit")
        cls.data = {"district": "Beji", "city": "Depok", "province": "West Java"}

    def setUp(self):
        self.client.force_login(self.owner)

    def test_location_requires_login_for_read_and_write(self):
        self.client.logout()
        for method in (self.client.get, self.client.post):
            response = method(self.url)
            self.assertRedirects(
                response, reverse("user_profile:login") + "?next=" + self.url
            )

    def test_save_and_reopen_location(self):
        response = self.client.post(self.url, self.data, follow=True)
        self.assertContains(response, "Your location has been updated.")
        self.assertContains(response, "Depok, West Java")
        response = self.client.get(self.url)
        self.assertEqual(response.context["form"]["district"].value(), "Beji")
        self.assertEqual(response.context["form"]["city"].value(), "Depok")
        self.assertEqual(response.context["form"]["province"].value(), "West Java")

    def test_city_and_province_are_required_but_district_is_optional(self):
        response = self.client.post(self.url, {"city": "   ", "province": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("city", response.context["form"].errors)
        self.assertIn("province", response.context["form"].errors)
        self.owner.profile.refresh_from_db()
        self.assertFalse(self.owner.profile.city)
        response = self.client.post(self.url, {**self.data, "district": ""})
        self.assertRedirects(response, reverse("user_profile:detail"))

    def test_submitted_owner_and_unrelated_fields_are_ignored(self):
        profile = self.owner.profile
        profile.bio = "Original bio"
        profile.profile_picture = "image/upload/v1/profile-picture"
        profile.save()
        self.client.post(
            self.url + f"?user_id={self.other.pk}",
            {
                **self.data,
                "user": self.other.pk,
                "display_name": "Changed",
                "bio": "Changed",
                "profile_picture": "Changed",
                "latitude": "12.34",
                "longitude": "56.78",
            },
        )
        profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(profile.user_id, self.owner.pk)
        self.assertEqual(profile.display_name, self.owner.username)
        self.assertEqual(profile.bio, "Original bio")
        self.assertEqual(profile.profile_picture.public_id, "profile-picture")
        self.assertIsNone(profile.latitude)
        self.assertIsNone(profile.longitude)
        self.assertFalse(self.other.profile.city)

    def test_changing_manual_area_clears_stale_coordinates(self):
        profile = self.owner.profile
        profile.latitude = -6.1
        profile.longitude = 106.8
        profile.save()
        self.client.post(self.url, self.data)
        profile.refresh_from_db()
        self.assertIsNone(profile.latitude)
        self.assertIsNone(profile.longitude)

    def test_location_form_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, self.data).status_code, 403)

    def test_profile_shows_location_link_and_empty_state(self):
        response = self.client.get(reverse("user_profile:detail"))
        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, "No location added yet.")
