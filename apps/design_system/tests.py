from django.test import TestCase
from django.urls import reverse


class DesignSystemViewTests(TestCase):
    def test_design_system_returns_ok(self):
        response = self.client.get(reverse("design_system:ds"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "design_system/ds.html")
        self.assertEqual(len(response.context["color_palettes"]), 6)
        self.assertEqual(
            sum(
                len(palette["swatches"])
                for palette in response.context["color_palettes"]
            ),
            63,
        )
        self.assertContains(response, "var(--color-primary-base)")
        self.assertContains(response, "var(--color-green-100)")
