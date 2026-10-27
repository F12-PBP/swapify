from django.test import TestCase
from django.urls import reverse


class HomeViewTests(TestCase):
    def test_homepage_returns_ok(self):
        response = self.client.get(reverse("main:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main/home.html")

    def test_safety_page_uses_catalog_marketplace_layout(self):
        response = self.client.get(reverse("main:safety"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "clothing_catalog/marketplace/base.html")

    def test_legacy_discover_redirect_preserves_filters(self):
        response = self.client.get(
            reverse("main:legacy_discover"),
            {"search": "denim", "size": "L", "page": "2"},
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response.url,
            reverse("clothing_catalog:list") + "?search=denim&size=L&page=2",
        )
