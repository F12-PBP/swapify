from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomeViewTests(TestCase):
    def test_homepage_returns_ok(self):
        response = self.client.get(reverse("main:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main/home.html")

    def test_discover_and_safety_are_public_and_use_marketplace_layout(self):
        for route in ("main:discover", "main:safety"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "marketplace/base.html")
                self.assertContains(response, reverse("clothing_catalog:my_list"))

    def test_setup_reminder_only_appears_for_incomplete_profile(self):
        route = reverse("main:discover")
        self.assertNotContains(self.client.get(route), "Finish my setup")
        user = get_user_model().objects.create_user(username="swapper")
        self.client.force_login(user)
        self.assertContains(self.client.get(route), "Finish my setup")
        user.profile.onboarding_completed = True
        user.profile.save(update_fields=["onboarding_completed"])
        self.assertNotContains(self.client.get(route), "Finish my setup")
