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

    def test_filters_combine_and_invalid_values_are_ignored(self):
        route = reverse("main:discover")
        response = self.client.get(
            route, {"type": "outerwear", "size": "L", "condition": "like_new"}
        )
        self.assertEqual(response.context["paginator"].count, 1)
        empty = self.client.get(route, {"size": "XS"})
        self.assertEqual(empty.context["paginator"].count, 0)
        invalid = self.client.get(
            route, {"type": "unknown", "sort": "name; DROP TABLE"}
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(invalid.context["paginator"].count, 1)
        self.assertContains(invalid, "Some filter values were invalid")

    def test_recommendations_use_preferences_and_newest_can_override(self):
        newer = Clothing.objects.create(
            owner=self.owner,
            name="Newest top",
            description="Top",
            type="top",
            size="M",
            condition="good",
        )
        self.viewer.profile.preferences = ["outerwear"]
        self.viewer.profile.save(update_fields=["preferences"])
        self.client.force_login(self.viewer)
        route = reverse("main:discover")
        recommended = self.client.get(route)
        self.assertEqual(
            list(recommended.context["clothing_items"]), [self.item, newer]
        )
        newest = self.client.get(route, {"sort": "newest"})
        self.assertEqual(list(newest.context["clothing_items"]), [newer, self.item])

    def test_nearby_filter_uses_saved_area_and_does_not_expose_coordinates(self):
        for user, latitude in ((self.viewer, -6.36), (self.owner, -6.37)):
            user.profile.latitude = latitude
            user.profile.longitude = 106.83
            user.profile.save(update_fields=["latitude", "longitude"])
        far_owner = get_user_model().objects.create_user(username="far-owner")
        far_owner.profile.latitude = -7.8
        far_owner.profile.longitude = 110.4
        far_owner.profile.save(update_fields=["latitude", "longitude"])
        far_item = Clothing.objects.create(
            owner=far_owner,
            name="A distant piece",
            description="Far away",
            type="top",
            size="M",
            condition="good",
        )
        unknown_owner = get_user_model().objects.create_user(username="unknown-area")
        unknown_item = Clothing.objects.create(
            owner=unknown_owner,
            name="No saved area",
            description="Unknown",
            type="top",
            size="M",
            condition="good",
        )
        self.client.force_login(self.viewer)
        route = reverse("main:discover")
        nearby = self.client.get(route, {"distance": "5"})
        self.assertEqual(list(nearby.context["clothing_items"]), [self.item])
        self.assertAlmostEqual(
            nearby.context["clothing_items"][0].distance_km, 1.112, places=2
        )
        self.assertNotContains(nearby, "106.83")
        self.assertNotContains(nearby, "-6.37")
        nearest = self.client.get(route, {"sort": "nearest"})
        self.assertEqual(
            list(nearest.context["clothing_items"]), [self.item, far_item, unknown_item]
        )

    def test_guest_distance_parameter_does_not_remove_listings(self):
        response = self.client.get(reverse("main:discover"), {"distance": "5"})
        self.assertEqual(response.context["paginator"].count, 1)
        self.assertFalse(response.context["has_location"])

    def test_location_save_returns_to_discover_but_rejects_external_return(self):
        self.client.force_login(self.viewer)
        route = reverse("user_profile:location_edit")
        data = {
            "district": "",
            "city": "Jakarta",
            "province": "Jakarta",
            "next": reverse("main:discover"),
        }
        response = self.client.post(route, data)
        self.assertRedirects(response, reverse("main:discover"))
        response = self.client.post(route, {**data, "next": "https://example.com/"})
        self.assertRedirects(response, reverse("user_profile:detail"))
