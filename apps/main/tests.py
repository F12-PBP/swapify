from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.clothing_catalog.models import Clothing


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


class DiscoveryViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="owner")
        cls.viewer = get_user_model().objects.create_user(username="viewer")
        cls.item = Clothing.objects.create(
            owner=cls.owner,
            name="Everyday denim jacket",
            description="Blue denim, ready for another chapter.",
            type=Clothing.Type.OUTERWEAR,
            size=Clothing.Size.L,
            condition=Clothing.Condition.LIKE_NEW,
        )

    def test_discovery_only_shows_available_items_from_other_swappers(self):
        Clothing.objects.create(
            owner=self.owner,
            name="Reserved boots",
            description="Boots",
            type="footwear",
            size="M",
            condition="good",
            status="reserved",
        )
        Clothing.objects.create(
            owner=self.viewer,
            name="My own shirt",
            description="Shirt",
            type="top",
            size="M",
            condition="good",
        )
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("main:discover"))
        self.assertContains(response, self.item.name)
        self.assertNotContains(response, "Reserved boots")
        self.assertNotContains(response, "My own shirt")
        self.assertContains(response, "New swapper")
        self.assertNotContains(response, "km away")

    def test_search_matches_description_and_handles_empty_results(self):
        response = self.client.get(reverse("main:discover"), {"search": "Blue denim"})
        self.assertContains(response, self.item.name)
        empty = self.client.get(reverse("main:discover"), {"search": "no-such-piece"})
        self.assertContains(empty, "No pieces match")

    def test_discovery_paginates_twelve_items_and_keeps_search(self):
        Clothing.objects.bulk_create(
            [
                Clothing(
                    owner=self.owner,
                    name=f"Denim {i}",
                    description="Denim",
                    type="top",
                    size="M",
                    condition="good",
                )
                for i in range(13)
            ]
        )
        response = self.client.get(reverse("main:discover"), {"search": "Denim"})
        self.assertEqual(len(response.context["clothing_items"]), 12)
        self.assertContains(response, "search=Denim&amp;page=2")
