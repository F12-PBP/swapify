from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.clothing_catalog.models import Clothing
from apps.swap_request.models import SwapRequest


class HomeViewTests(TestCase):
    def test_homepage_returns_ok(self):
        response = self.client.get(reverse("main:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main/home.html")

    def test_safety_page_uses_shared_marketplace_layout(self):
        response = self.client.get(reverse("main:safety"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "marketplace/base.html")

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


class LandingDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="landing-owner")
        cls.viewer = get_user_model().objects.create_user(username="landing-viewer")
        cls.pieces = [
            Clothing.objects.create(
                owner=cls.owner,
                name=f"Available piece {index}",
                type="top",
                size="M",
                condition="good",
            )
            for index in range(5)
        ]
        for status in (Clothing.Status.RESERVED, Clothing.Status.SWAPPED):
            Clothing.objects.create(
                owner=cls.owner,
                name=f"Unavailable {status}",
                type="top",
                size="M",
                condition="good",
                status=status,
            )

    def test_discovery_links_to_four_available_pieces(self):
        response = self.client.get(reverse("main:home"))
        self.assertEqual(
            [piece.pk for piece in response.context["featured_clothing"]],
            [piece.pk for piece in reversed(self.pieces[1:])],
        )
        self.assertFalse(response.context["inspiration_pieces"])
        for piece in self.pieces[1:]:
            self.assertContains(response, f'href="{piece.get_absolute_url()}"')
        self.assertNotContains(response, "Unavailable reserved")
        self.assertNotContains(response, "Unavailable swapped")

    def test_viewer_does_not_see_their_own_piece_as_a_swap_option(self):
        own = Clothing.objects.create(
            owner=self.viewer,
            name="My own piece",
            type="top",
            size="M",
            condition="good",
        )
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("main:home"))
        self.assertNotIn(own, response.context["featured_clothing"])
        self.assertContains(response, "Visit my wardrobe")

    def test_sparse_catalog_keeps_four_cards_with_labeled_inspiration(self):
        Clothing.objects.exclude(pk=self.pieces[0].pk).delete()
        response = self.client.get(reverse("main:home"))
        self.assertEqual(len(response.context["featured_clothing"]), 1)
        self.assertEqual(len(response.context["inspiration_pieces"]), 3)
        self.assertContains(response, "Illustration · photo unavailable", count=1)
        self.assertContains(response, "Style inspiration", count=3)

    def test_empty_catalog_still_has_clothing_and_a_real_catalog_link(self):
        Clothing.objects.all().delete()
        response = self.client.get(reverse("main:home"))
        self.assertFalse(response.context["featured_clothing"])
        self.assertEqual(len(response.context["inspiration_pieces"]), 4)
        self.assertContains(response, "Style inspiration", count=4)
        self.assertContains(response, f'href="{reverse("clothing_catalog:list")}"')
        self.assertContains(response, "Just a demo. No items are exchanged.")
        self.assertContains(response, "not exact or live locations")
        self.assertContains(response, "Example profile")


class MarketplaceLayoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="alex")
        cls.partner = get_user_model().objects.create_user(username="nadia")
        cls.offered = Clothing.objects.create(
            owner=cls.user, name="Linen shirt", type="top", size="M", condition="good"
        )
        cls.requested = Clothing.objects.create(
            owner=cls.partner,
            name="Denim jacket",
            type="outerwear",
            size="M",
            condition="good",
        )
        cls.swap = SwapRequest.objects.create(
            requester=cls.user,
            offered_clothing=cls.offered,
            requested_clothing=cls.requested,
            status=SwapRequest.Status.ACCEPTED,
        )

    def test_marketplace_pages_share_layout_and_mark_the_current_section(self):
        self.client.force_login(self.user)
        wardrobe_url = reverse("user_profile:public", args=[self.user.username])
        sections = {
            "discover": reverse("clothing_catalog:list"),
            "swaps": reverse("swap_request:list"),
            "messages": reverse("chat:list"),
            "wardrobe": wardrobe_url,
        }
        pages = [
            (sections["discover"], "discover"),
            (self.requested.get_absolute_url(), "discover"),
            (sections["swaps"], "swaps"),
            (self.swap.get_absolute_url(), "swaps"),
            (sections["messages"], "messages"),
            (reverse("chat:detail", args=[self.swap.chat_room.pk]), "messages"),
            (wardrobe_url, "wardrobe"),
            (reverse("user_profile:detail"), "wardrobe"),
            (reverse("user_profile:edit"), "wardrobe"),
            (reverse("user_profile:location_edit"), "wardrobe"),
            (reverse("clothing_catalog:my_list"), "wardrobe"),
            (reverse("clothing_catalog:create"), "wardrobe"),
        ]
        for url, section in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "marketplace/base.html")
                self.assertTemplateUsed(response, "components/marketplace/header.html")
                self.assertNotContains(response, 'aria-label="Main navigation"')
                self.assertContains(response, 'aria-label="Marketplace"', count=1)
                self.assertContains(
                    response,
                    f'href="{sections[section]}" '
                    'class="market-nav border-primary-base text-primary-base" '
                    'aria-current="page"',
                )
                self.assertContains(
                    response, 'src="/static/main/js/marketplace-navbar.js', count=1
                )

    def test_public_profile_uses_viewer_navigation_and_keeps_clothing_management(self):
        self.client.force_login(self.user)
        own = self.client.get(reverse("user_profile:public", args=[self.user.username]))
        self.assertContains(own, "Manage clothing")
        other = self.client.get(
            reverse("user_profile:public", args=[self.partner.username])
        )
        self.assertNotContains(other, "Manage clothing")
        own_url = reverse("user_profile:public", args=[self.user.username])
        self.assertContains(other, f'href="{own_url}" class="market-nav')
        self.client.logout()
        anonymous = self.client.get(
            reverse("user_profile:public", args=[self.partner.username])
        )
        self.assertEqual(anonymous.status_code, 200)
        self.assertTemplateUsed(anonymous, "marketplace/base.html")

    def test_profile_success_message_is_rendered_once_by_the_shared_layout(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("user_profile:edit"),
            {"display_name": "Alex", "bio": "Swapping favourites"},
            follow=True,
        )
        self.assertContains(response, "Your profile has been updated.", count=1)
