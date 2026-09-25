from django.test import TestCase

# Create your tests here.
from django.urls import reverse


class HomeViewTests(TestCase):
    def test_homepage_returns_ok(self):
        response = self.client.get(reverse("main:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main/home.html")

    def test_design_system_returns_ok(self):
        response = self.client.get(reverse("main:ds"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main/ds.html")
