import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import ClothingForm
from .models import Clothing


class ClothingViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner", password="password123"
        )
        self.other_user = get_user_model().objects.create_user(
            username="other", password="password123"
        )
        self.clothing = Clothing.objects.create(
            owner=self.owner,
            name="Linen Shirt",
            description="Cream-colored linen shirt.",
            type=Clothing.Type.TOP,
            size=Clothing.Size.M,
            condition=Clothing.Condition.GOOD,
        )

    def test_clothing_items_have_unique_uuid_fields_and_integer_primary_keys(self):
        another_item = Clothing.objects.create(
            owner=self.owner,
            name="Canvas Jacket",
            description="A durable jacket.",
            type=Clothing.Type.OUTERWEAR,
            size=Clothing.Size.M,
            condition=Clothing.Condition.GOOD,
        )

        self.assertIsInstance(self.clothing.uuid, uuid.UUID)
        self.assertIsInstance(another_item.uuid, uuid.UUID)
        self.assertNotEqual(self.clothing.uuid, another_item.uuid)
        self.assertIsInstance(self.clothing.pk, int)

    def test_clothing_uuid_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Clothing.objects.create(
                    owner=self.owner,
                    name="Duplicate UUID",
                    description="UUID values must be unique.",
                    type=Clothing.Type.TOP,
                    size=Clothing.Size.M,
                    condition=Clothing.Condition.GOOD,
                    uuid=self.clothing.uuid,
                )

    def test_catalog_shows_empty_state(self):
        self.clothing.delete()

        response = self.client.get(reverse("clothing_catalog:list"))

        self.assertContains(response, "No pieces match this search yet.")
        self.assertEqual(response.context["paginator"].count, 0)
        self.assertTemplateUsed(response, "clothing_catalog/clothing_list.html")

    def test_catalog_and_detail_are_public(self):
        list_response = self.client.get(reverse("clothing_catalog:list"))
        detail_response = self.client.get(
            reverse("clothing_catalog:detail", args=[self.clothing.pk])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, self.clothing.name)
        self.assertTemplateUsed(list_response, "clothing_catalog/clothing_list.html")
        self.assertTemplateUsed(list_response, "marketplace/base.html")
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "marketplace/base.html")
        self.assertContains(detail_response, self.clothing.description)

    def test_personal_wardrobe_keeps_own_reserved_items_and_status_filters(self):
        self.clothing.status = Clothing.Status.RESERVED
        self.clothing.save(update_fields=["status"])
        Clothing.objects.create(
            owner=self.other_user,
            name="Another swapper's item",
            description="Not mine",
            type="top",
            size="M",
            condition="good",
        )
        self.client.force_login(self.owner)
        route = reverse("clothing_catalog:my_list")
        response = self.client.get(route)
        self.assertTemplateUsed(response, "clothing_catalog/wardrobe.html")
        self.assertEqual(list(response.context["clothing_items"]), [self.clothing])
        available = self.client.get(route, {"status": "available"})
        self.assertEqual(list(available.context["clothing_items"]), [])

    def test_item_detail_uses_its_owner_and_only_available_related_items(self):
        related = Clothing.objects.create(
            owner=self.owner,
            name="Another linen shirt",
            description="Linen",
            type="top",
            size="M",
            condition="good",
        )
        Clothing.objects.create(
            owner=self.owner,
            name="A reserved shirt",
            description="Reserved",
            type="top",
            size="M",
            condition="good",
            status="reserved",
        )
        response = self.client.get(self.clothing.get_absolute_url())
        self.assertEqual(list(response.context["related_items"]), [related])
        self.assertContains(
            response, reverse("user_profile:public", args=[self.owner.username])
        )
        self.assertContains(response, "Propose a swap")
        self.client.force_login(self.owner)
        own = self.client.get(self.clothing.get_absolute_url())
        self.assertContains(own, "Edit item")
        self.assertNotContains(
            own, reverse("swap_request:create", args=[self.clothing.pk])
        )

    def test_related_finds_prioritize_category_and_fill_four_unique_available_items(
        self,
    ):
        same_category = Clothing.objects.create(
            owner=self.owner,
            name="Another shirt",
            type="top",
            size="M",
            condition="good",
            description="A related piece",
        )
        for index in range(5):
            Clothing.objects.create(
                owner=self.other_user,
                name=f"Jacket {index}",
                type="outerwear",
                size="M",
                condition="good",
                description="Another available find",
            )
        response = self.client.get(self.clothing.get_absolute_url())
        related = list(response.context["related_items"])
        self.assertEqual(len(related), 4)
        self.assertEqual(related[0], same_category)
        self.assertEqual(len({item.pk for item in related}), 4)
        self.assertNotIn(self.clothing, related)
        self.client.force_login(self.other_user)
        owned = self.client.get(self.clothing.get_absolute_url())
        self.assertEqual(list(owned.context["related_items"]), [same_category])

    def test_related_finds_section_stays_visible_when_no_alternatives_exist(self):
        response = self.client.get(self.clothing.get_absolute_url())
        self.assertContains(response, "More lovely finds out there")
        self.assertContains(response, "More lovely finds are on their way.")

    def test_authenticated_user_becomes_owner_when_creating_clothing(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("clothing_catalog:create"),
            {
                "name": "Denim Jacket",
                "description": "Blue denim jacket.",
                "type": Clothing.Type.OUTERWEAR,
                "size": Clothing.Size.L,
                "condition": Clothing.Condition.GOOD,
                "status": Clothing.Status.AVAILABLE,
            },
        )

        clothing = Clothing.objects.get(name="Denim Jacket")
        self.assertRedirects(response, clothing.get_absolute_url())
        self.assertEqual(clothing.owner, self.owner)

    def test_adding_an_offer_can_return_to_swap_and_rejects_external_return(self):
        self.client.force_login(self.owner)
        swap_url = reverse("swap_request:create", args=[self.clothing.pk])
        data = {
            "name": "New offer",
            "description": "Ready to swap",
            "type": "top",
            "size": "M",
            "condition": "good",
        }
        response = self.client.post(
            reverse("clothing_catalog:create") + "?next=" + swap_url, data
        )
        self.assertEqual(response.url, swap_url)
        existing_ids = set(Clothing.objects.values_list("pk", flat=True))
        external = self.client.post(
            reverse("clothing_catalog:create") + "?next=https://example.com/", data
        )
        new_offer = Clothing.objects.exclude(pk__in=existing_ids).get()
        self.assertEqual(external.url, new_offer.get_absolute_url())

    def test_create_form_prevents_repeated_submission(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("clothing_catalog:create"))

        self.assertContains(response, "data-submit-once")
        self.assertContains(response, 'data-submitting-label="Adding..."')
        self.assertContains(response, ">Add</button>")

    def test_edit_form_keeps_save_labels(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("clothing_catalog:update", args=[self.clothing.pk])
        )

        self.assertContains(response, 'data-submitting-label="Saving..."')
        self.assertContains(response, ">Save</button>")

    def test_non_owner_cannot_update_or_delete_clothing(self):
        self.client.force_login(self.other_user)

        update_response = self.client.get(
            reverse("clothing_catalog:update", args=[self.clothing.pk])
        )
        delete_response = self.client.post(
            reverse("clothing_catalog:delete", args=[self.clothing.pk])
        )

        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(Clothing.objects.filter(pk=self.clothing.pk).exists())

    def test_owner_cannot_update_or_delete_reserved_or_swapped_clothing(self):
        self.client.force_login(self.owner)

        for status in (Clothing.Status.RESERVED, Clothing.Status.SWAPPED):
            with self.subTest(status=status):
                self.clothing.status = status
                self.clothing.save()
                update_response = self.client.post(
                    reverse("clothing_catalog:update", args=[self.clothing.pk]),
                    {
                        "name": "Changed name",
                        "description": "Changed description",
                        "type": Clothing.Type.TOP,
                        "size": Clothing.Size.M,
                        "condition": Clothing.Condition.GOOD,
                    },
                )
                delete_response = self.client.post(
                    reverse("clothing_catalog:delete", args=[self.clothing.pk])
                )

                self.assertEqual(update_response.status_code, 403)
                self.assertEqual(delete_response.status_code, 403)
                self.clothing.refresh_from_db()
                self.assertEqual(self.clothing.name, "Linen Shirt")
                self.assertTrue(Clothing.objects.filter(pk=self.clothing.pk).exists())

    def test_clothing_form_does_not_expose_status(self):
        self.assertNotIn("status", ClothingForm().fields)

    def test_catalog_filters_and_search(self):
        Clothing.objects.create(
            owner=self.owner,
            name="Wool Coat",
            description="Warm coat.",
            type=Clothing.Type.OUTERWEAR,
            size=Clothing.Size.L,
            condition=Clothing.Condition.NEW,
        )

        response = self.client.get(
            reverse("clothing_catalog:list"),
            {
                "search": "Linen",
                "type": Clothing.Type.TOP,
                "size": Clothing.Size.M,
                "condition": Clothing.Condition.GOOD,
                "status": Clothing.Status.AVAILABLE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Linen Shirt")
        self.assertNotContains(response, "Wool Coat")

    def test_my_clothing_requires_login_and_lists_only_owners_items(self):
        response = self.client.get(reverse("clothing_catalog:my_list"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.owner)
        Clothing.objects.create(
            owner=self.other_user,
            name="Other Item",
            description="Not mine.",
            type=Clothing.Type.TOP,
            size=Clothing.Size.S,
            condition=Clothing.Condition.FAIR,
        )
        response = self.client.get(reverse("clothing_catalog:my_list"))

        self.assertContains(response, "Linen Shirt")
        self.assertNotContains(response, "Other Item")

    def test_pagination_preserves_filters(self):
        for index in range(12):
            Clothing.objects.create(
                owner=self.owner,
                name=f"Shirt {index}",
                description="Another linen shirt.",
                type=Clothing.Type.TOP,
                size=Clothing.Size.M,
                condition=Clothing.Condition.GOOD,
            )

        response = self.client.get(
            reverse("clothing_catalog:list"),
            {"search": "linen", "type": Clothing.Type.TOP, "page": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertContains(response, "search=linen")
        self.assertContains(response, "type=top")


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
        response = self.client.get(reverse("clothing_catalog:list"))
        self.assertContains(response, self.item.name)
        self.assertNotContains(response, "Reserved boots")
        self.assertNotContains(response, "My own shirt")
        self.assertContains(response, "New swapper")
        self.assertNotContains(response, "km away")

    def test_search_matches_description_and_handles_empty_results(self):
        response = self.client.get(
            reverse("clothing_catalog:list"), {"search": "Blue denim"}
        )
        self.assertContains(response, self.item.name)
        empty = self.client.get(
            reverse("clothing_catalog:list"), {"search": "no-such-piece"}
        )
        self.assertContains(empty, "No pieces match")

    def test_see_all_finds_link_navigates_to_full_unfiltered_catalog(self):
        response = self.client.get(
            reverse("clothing_catalog:list"), {"search": "no-such-piece"}
        )

        self.assertRegex(
            response.content.decode(),
            r'<a class="market-secondary text-b8" '
            r'href="/clothing-catalog/#finds">See all finds</a>',
        )

    def test_live_search_returns_only_results_and_current_filter_state(self):
        response = self.client.get(
            reverse("clothing_catalog:list"),
            {"search": "denim", "type": "outerwear", "size": "L"},
            HTTP_X_CATALOG_REQUEST="results",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertIn(self.item.name, data["html"])
        self.assertNotIn("<!DOCTYPE", data["html"])
        self.assertNotIn("Your next favourite.", data["html"])
        self.assertEqual(data["filters"]["search"], "denim")
        self.assertEqual(data["filters"]["sort"], "recommended")
        self.assertEqual(data["errors"], {})
        self.assertIn("X-Catalog-Request", response["Vary"])
        page = self.client.get(reverse("clothing_catalog:list"))
        self.assertIn("X-Catalog-Request", page["Vary"])

    def test_live_search_empty_and_invalid_filter_responses(self):
        route = reverse("clothing_catalog:list")
        empty = self.client.get(
            route, {"search": "missing-piece"}, HTTP_X_CATALOG_REQUEST="results"
        ).json()
        self.assertEqual(empty["count"], 0)
        self.assertIn("No pieces match", empty["html"])
        invalid = self.client.get(
            route, {"type": "unknown"}, HTTP_X_CATALOG_REQUEST="results"
        ).json()
        self.assertEqual(invalid["count"], 1)
        self.assertIn("type", invalid["errors"])
        self.assertNotIn("type", invalid["filters"])

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
        response = self.client.get(
            reverse("clothing_catalog:list"), {"search": "Denim"}
        )
        self.assertEqual(len(response.context["clothing_items"]), 12)
        self.assertContains(response, "search=Denim&amp;page=2")

    def test_filters_combine_and_invalid_values_are_ignored(self):
        route = reverse("clothing_catalog:list")
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
        route = reverse("clothing_catalog:list")
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
        route = reverse("clothing_catalog:list")
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
        response = self.client.get(reverse("clothing_catalog:list"), {"distance": "5"})
        self.assertEqual(response.context["paginator"].count, 1)
        self.assertFalse(response.context["has_location"])

    def test_location_save_returns_to_discover_but_rejects_external_return(self):
        self.client.force_login(self.viewer)
        route = reverse("user_profile:location_edit")
        data = {
            "district": "",
            "city": "Jakarta",
            "province": "Jakarta",
            "next": reverse("clothing_catalog:list"),
        }
        response = self.client.post(route, data)
        self.assertRedirects(response, reverse("clothing_catalog:list"))
        response = self.client.post(route, {**data, "next": "https://example.com/"})
        self.assertRedirects(response, reverse("user_profile:detail"))

    def test_setup_reminder_only_appears_for_incomplete_profile(self):
        route = reverse("clothing_catalog:list")
        self.assertNotContains(self.client.get(route), "Finish my setup")
        user = get_user_model().objects.create_user(username="swapper")
        self.client.force_login(user)
        self.assertContains(self.client.get(route), "Finish my setup")
        user.profile.onboarding_completed = True
        user.profile.save(update_fields=["onboarding_completed"])
        self.assertNotContains(self.client.get(route), "Finish my setup")
