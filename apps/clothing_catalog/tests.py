from django.contrib.auth import get_user_model
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

    def test_catalog_shows_empty_state(self):
        self.clothing.delete()

        response = self.client.get(reverse("clothing_catalog:list"))

        self.assertContains(response, "No clothing found.")
        self.assertContains(response, "Try adjusting your search or filter parameters.")

    def test_catalog_and_detail_are_public(self):
        list_response = self.client.get(reverse("clothing_catalog:list"))
        detail_response = self.client.get(
            reverse("clothing_catalog:detail", args=[self.clothing.pk])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, self.clothing.name)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "marketplace/base.html")
        self.assertContains(detail_response, self.clothing.description)

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
        external = self.client.post(
            reverse("clothing_catalog:create") + "?next=https://example.com/", data
        )
        self.assertEqual(external.url, Clothing.objects.latest("pk").get_absolute_url())

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
