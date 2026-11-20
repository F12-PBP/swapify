import io
from unittest.mock import patch

from cloudinary import CloudinaryResource
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from .models import Clothing


class ClothingAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="catalog-owner", password="test-password"
        )
        self.other_user = user_model.objects.create_user(
            username="catalog-other", password="test-password"
        )
        self.clothing = Clothing.objects.create(
            owner=self.owner,
            name="Linen Shirt",
            description="Cream linen shirt.",
            type=Clothing.Type.TOP,
            size=Clothing.Size.M,
            condition=Clothing.Condition.GOOD,
        )
        self.detail_url = reverse(
            "clothing_catalog_api:clothing-detail", args=[self.clothing.uuid]
        )
        self.list_url = reverse("clothing_catalog_api:clothing-list")
        self.my_list_url = reverse("clothing_catalog_api:my-clothing-list")

    def photo(self):
        image = io.BytesIO()
        Image.new("RGB", (12, 12), "blue").save(image, format="PNG")
        return SimpleUploadedFile("shirt.png", image.getvalue(), "image/png")

    def test_public_catalog_and_detail_return_clothing(self):
        listed = self.client.get(self.list_url)
        detail = self.client.get(self.detail_url)

        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["results"][0]["uuid"], str(self.clothing.uuid))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["name"], self.clothing.name)

    def test_my_clothing_requires_login_and_only_returns_owner_items(self):
        self.assertEqual(
            self.client.get(self.my_list_url).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.my_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["uuid"] for item in response.data["results"]],
            [str(self.clothing.uuid)],
        )

    def test_create_requires_login_and_image(self):
        self.assertEqual(
            self.client.post(self.list_url, {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.list_url,
            {
                "name": "No photo",
                "description": "Missing image.",
                "type": Clothing.Type.TOP,
                "size": Clothing.Size.M,
                "condition": Clothing.Condition.GOOD,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_image", response.data)
        self.assertEqual(Clothing.objects.count(), 1)

    @patch("apps.clothing_catalog.serializers.upload_image")
    def test_owner_can_create_clothing_with_validated_photo(self, upload_image):
        upload_image.return_value = CloudinaryResource(
            "wardrobe/new-shirt", resource_type="image"
        )
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            self.list_url,
            {
                "name": "New shirt",
                "description": "Blue cotton shirt.",
                "type": Clothing.Type.TOP,
                "size": Clothing.Size.M,
                "condition": Clothing.Condition.GOOD,
                "new_image": self.photo(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["owner"], self.owner.username)
        self.assertEqual(response.data["status"], Clothing.Status.AVAILABLE)
        self.assertEqual(Clothing.objects.count(), 2)
        upload_image.assert_called_once()

    def test_owner_can_patch_and_delete_available_clothing(self):
        self.client.force_authenticate(self.owner)
        updated = self.client.patch(
            self.detail_url, {"name": "Updated shirt"}, format="json"
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.clothing.refresh_from_db()
        self.assertEqual(self.clothing.name, "Updated shirt")

        deleted = self.client.delete(self.detail_url)
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Clothing.objects.filter(pk=self.clothing.pk).exists())

    def test_other_user_cannot_patch_or_delete_clothing(self):
        self.client.force_authenticate(self.other_user)

        patched = self.client.patch(
            self.detail_url, {"name": "Hijacked"}, format="json"
        )
        deleted = self.client.delete(self.detail_url)

        self.assertEqual(patched.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(deleted.status_code, status.HTTP_403_FORBIDDEN)
        self.clothing.refresh_from_db()
        self.assertEqual(self.clothing.name, "Linen Shirt")
        self.assertTrue(Clothing.objects.filter(pk=self.clothing.pk).exists())

    def test_reserved_clothing_cannot_be_changed_or_deleted(self):
        self.clothing.status = Clothing.Status.RESERVED
        self.clothing.save(update_fields=["status"])
        self.client.force_authenticate(self.owner)

        patched = self.client.patch(self.detail_url, {"name": "Changed"}, format="json")
        deleted = self.client.delete(self.detail_url)

        self.assertEqual(patched.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(deleted.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Clothing.objects.filter(pk=self.clothing.pk).exists())
