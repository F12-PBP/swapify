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

    def test_catalog_and_detail_are_public(self):
        list_response = self.client.get(reverse("clothing_catalog:list"))
        detail_response = self.client.get(
            reverse("clothing_catalog:detail", args=[self.clothing.pk])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, self.clothing.name)
        self.assertEqual(detail_response.status_code, 200)

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
