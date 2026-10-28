import json
import time
from datetime import timedelta
from importlib import import_module
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from cloudinary import CloudinaryImage
from cloudinary.exceptions import AuthorizationRequired, NotAllowed
from cloudinary.exceptions import Error as CloudinaryError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.clothing_catalog.models import Clothing
from apps.review_rating.models import Review
from apps.swap_request.models import SwapRequest
from apps.transaction.models import Transaction
from common.images import MAX_IMAGE_BYTES, ImageUploadError, upload_image

from .forms import ProfileLocationForm
from .geocoding import (
    GATE_KEY,
    AreaNotFound,
    GeocodingBusy,
    GeocodingError,
    reverse_geocode,
)
from .models import GeocodingCacheEntry, Profile
from .services import ProfilePhotoUploadError, upload_profile_picture
from .views import PublicProfileDetailView

PASSWORD = "Swapify-Check!2026-audit"


def image_upload(image_format="PNG", byte_size=None):
    stream = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(stream, format=image_format)
    contents = stream.getvalue()
    if byte_size:
        contents = contents.ljust(byte_size, b"0")
    return SimpleUploadedFile(f"photo.{image_format.lower()}", contents)


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="existing_member", password=PASSWORD
        )

    def register(self, **overrides):
        data = {
            "username": "new_member",
            "name": "New Member",
            "community_agreement": "on",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("user_profile:register"), data)

    def test_registration_creates_user_and_exactly_one_profile(self):
        response = self.register()
        self.assertRedirects(response, reverse("user_profile:onboarding"))
        user = get_user_model().objects.get(username="new_member")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        self.assertEqual(user.profile.display_name, "New Member")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_registration_rejects_duplicate_username(self):
        response = self.register(username=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_registration_rejects_mismatched_or_weak_passwords(self):
        for password1, password2 in ((PASSWORD, "different"), ("123", "123")):
            with self.subTest(password=password1):
                response = self.register(password1=password1, password2=password2)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(
                    get_user_model().objects.filter(username="new_member").exists()
                )

    def test_profile_creation_failure_rolls_back_user_registration(self):
        with patch("apps.user_profile.signals.Profile.objects.using") as manager:
            manager.return_value.get_or_create.side_effect = RuntimeError(
                "Profile write failed"
            )
            with self.assertRaises(RuntimeError):
                self.register()
        self.assertFalse(
            get_user_model().objects.filter(username="new_member").exists()
        )

    def test_signal_does_not_duplicate_or_overwrite_profile_on_user_save(self):
        profile = self.user.profile
        profile.display_name = "My chosen name"
        profile.save()
        self.user.email = "member@example.com"
        self.user.save()
        profile.refresh_from_db()
        self.assertEqual(Profile.objects.filter(user=self.user).count(), 1)
        self.assertEqual(profile.display_name, "My chosen name")

    def test_login_pages_load_and_invalid_login_shows_errors(self):
        for name in ("login", "register"):
            self.assertEqual(
                self.client.get(reverse(f"user_profile:{name}")).status_code, 200
            )
        response = self.client.post(
            reverse("user_profile:login"),
            {"username": self.user.username, "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            reverse("user_profile:login"),
            {"username": self.user.username, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_redirects_to_own_profile_by_default(self):
        response = self.client.post(
            reverse("user_profile:login"),
            {"username": self.user.username, "password": PASSWORD},
        )
        self.assertRedirects(response, reverse("user_profile:detail"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_login_returns_to_original_protected_module(self):
        destination = reverse("swap_request:list")
        response = self.client.get(destination)
        self.assertRedirects(
            response, reverse("user_profile:login") + "?next=" + destination
        )
        response = self.client.post(
            reverse("user_profile:login"),
            {
                "username": self.user.username,
                "password": PASSWORD,
                "next": destination,
            },
        )
        self.assertRedirects(response, destination)

    def test_external_next_destination_is_rejected(self):
        for destination in ("https://example.com/", "//example.com/"):
            self.client.logout()
            response = self.client.post(
                reverse("user_profile:login"),
                {
                    "username": self.user.username,
                    "password": PASSWORD,
                    "next": destination,
                },
            )
            self.assertRedirects(response, reverse("user_profile:detail"))

    def test_profile_is_private_and_ignores_submitted_user_id(self):
        destination = reverse("user_profile:detail")
        response = self.client.get(destination)
        self.assertEqual(response.status_code, 302)
        other = get_user_model().objects.create_user(username="other_member")
        self.client.force_login(self.user)
        response = self.client.get(destination, {"user_id": other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile"].user_id, self.user.pk)

    def test_authenticated_users_are_redirected_from_auth_forms(self):
        self.client.force_login(self.user)
        for name in ("login", "register"):
            response = self.client.get(reverse(f"user_profile:{name}"))
            self.assertRedirects(response, reverse("user_profile:detail"))
        self.register()
        self.assertFalse(
            get_user_model().objects.filter(username="new_member").exists()
        )

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.user)
        destination = reverse("user_profile:logout")
        self.assertEqual(self.client.get(destination).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(destination), reverse("main:home"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.get(reverse("user_profile:detail")).status_code, 302
        )

    def test_registration_login_and_logout_require_csrf_tokens(self):
        client = Client(enforce_csrf_checks=True)
        for name in ("register", "login"):
            self.assertEqual(
                client.post(reverse(f"user_profile:{name}"), {}).status_code, 403
            )
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("user_profile:logout")).status_code, 403)
        client.get(reverse("user_profile:detail"))
        response = client.post(
            reverse("user_profile:logout"),
            {"csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(response.status_code, 302)

    def test_navigation_reflects_authentication_state(self):
        response = self.client.get(reverse("main:home"))
        self.assertContains(response, "Sign In")
        self.assertNotContains(response, "My Profile")
        self.client.force_login(self.user)
        response = self.client.get(reverse("main:home"))
        self.assertContains(response, "My Profile")
        self.assertContains(response, "Log Out")
        self.assertContains(response, reverse("swap_request:list"))
        self.assertContains(response, reverse("chat:list"))
        self.assertNotContains(response, "Sign In")

    def test_development_does_not_automatically_authenticate_visitors(self):
        get_user_model().objects.create_user(username="testuser1")
        self.assertNotIn(
            "apps.main.middleware.AutoLoginMiddleware", settings.MIDDLEWARE
        )
        response = self.client.get(reverse("main:home"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class ProfileBackfillTests(TestCase):
    def test_backfill_restores_missing_profiles_and_preserves_existing_data(self):
        user_model = get_user_model()
        existing = user_model.objects.create_user(username="existing_profile")
        existing.profile.display_name = "Keep my name"
        existing.profile.bio = "Keep my bio"
        existing.profile.save()
        missing = user_model.objects.create_user(username="legacy_member")
        missing.profile.delete()
        historical_apps = MigrationExecutor(connection).loader.project_state().apps
        migration = import_module(
            "apps.user_profile.migrations.0002_backfill_missing_profiles"
        )
        editor = SimpleNamespace(connection=connection)
        migration.backfill_missing_profiles(historical_apps, editor)
        migration.backfill_missing_profiles(historical_apps, editor)
        self.assertEqual(Profile.objects.filter(user=missing).count(), 1)
        self.assertEqual(
            Profile.objects.get(user=missing).display_name, "legacy_member"
        )
        preserved = Profile.objects.get(user=existing)
        self.assertEqual(preserved.display_name, "Keep my name")
        self.assertEqual(preserved.bio, "Keep my bio")


class AuthenticatedExchangeFlowTests(TestCase):
    def test_two_registered_users_can_complete_an_exchange(self):
        requester, owner = Client(), Client()
        for client, username in ((requester, "alice"), (owner, "bob")):
            response = client.post(
                reverse("user_profile:register"),
                {
                    "username": username,
                    "name": username,
                    "community_agreement": "on",
                    "password1": PASSWORD,
                    "password2": PASSWORD,
                },
            )
            self.assertEqual(response.status_code, 302)
            response = client.post(
                reverse("user_profile:login"),
                {"username": username, "password": PASSWORD},
            )
            self.assertEqual(response.status_code, 302)
            response = client.post(
                reverse("clothing_catalog:create"),
                {
                    "name": f"{username}'s shirt",
                    "description": "Good condition",
                    "type": Clothing.Type.TOP,
                    "size": Clothing.Size.M,
                    "condition": Clothing.Condition.GOOD,
                    "status": Clothing.Status.AVAILABLE,
                },
            )
            self.assertEqual(response.status_code, 302)
        offered = Clothing.objects.get(owner__username="alice")
        requested = Clothing.objects.get(owner__username="bob")
        create_url = reverse("swap_request:create", args=[requested.pk])
        self.assertContains(requester.get(requested.get_absolute_url()), create_url)
        response = requester.post(create_url, {"offered_clothing": offered.pk})
        self.assertEqual(response.status_code, 302)
        swap = SwapRequest.objects.get(requester__username="alice")
        response = owner.post(reverse("swap_request:accept", args=[swap.pk]))
        self.assertEqual(response.status_code, 302)
        swap.refresh_from_db()
        room = swap.chat_room
        exchange = swap.transaction
        response = requester.get(swap.get_absolute_url())
        self.assertContains(response, reverse("chat:detail", args=[room.pk]))
        self.assertContains(response, reverse("transaction_detail", args=[exchange.pk]))
        response = requester.post(
            reverse("chat:send", args=[room.pk]), {"message": "Meet at campus?"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(
            owner.get(reverse("chat:detail", args=[room.pk])), "Meet at campus?"
        )
        response = owner.post(
            reverse("transaction_update", args=[exchange.pk]),
            {
                "method": Transaction.Method.MEETUP,
                "meetup_date": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                "meetup_location": "Campus entrance",
            },
        )
        self.assertEqual(response.status_code, 302)
        owner.post(reverse("transaction_start", args=[exchange.pk]))
        for client in (owner, requester):
            response = client.post(reverse("transaction_received", args=[exchange.pk]))
            self.assertEqual(response.status_code, 302)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, Transaction.Status.COMPLETED)
        self.assertIsNotNone(exchange.completed_at)
        self.assertEqual(
            Clothing.objects.filter(status=Clothing.Status.SWAPPED).count(), 2
        )
        self.assertEqual(Profile.objects.count(), 2)
        review_url = reverse("review_rating:create", args=[exchange.pk])
        for client, rating in ((requester, 5), (owner, 4)):
            response = client.post(
                review_url,
                {"rating": rating, "comment": "Great exchange!"},
                follow=True,
            )
            self.assertContains(response, "Your review has been submitted.")
            self.assertNotContains(response, "Write a Review")
        self.assertEqual(Review.objects.filter(transaction=exchange).count(), 2)
        for username, average in (("alice", 4), ("bob", 5)):
            response = Client().get(reverse("user_profile:public", args=[username]))
            self.assertEqual(
                response.context["rating_summary"], {"average": average, "count": 1}
            )


class ProfileEditingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="profile_owner")
        cls.other = get_user_model().objects.create_user(username="other_profile")

    def test_anonymous_users_cannot_edit(self):
        url = reverse("user_profile:edit")

        for method in ("get", "post"):
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 302)

    def test_edit_changes_only_current_users_allowed_fields(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("user_profile:edit"),
            {
                "display_name": "Nama Baru",
                "bio": "Suka bertukar pakaian.",
                "user": self.other.pk,
                "user_id": self.other.pk,
                "latitude": "10",
            },
        )

        self.assertRedirects(
            response,
            reverse("user_profile:detail"),
        )

        self.owner.profile.refresh_from_db()
        self.other.profile.refresh_from_db()

        self.assertEqual(
            self.owner.profile.display_name,
            "Nama Baru",
        )
        self.assertEqual(
            self.owner.profile.user_id,
            self.owner.pk,
        )
        self.assertIsNone(self.owner.profile.latitude)
        self.assertEqual(
            self.other.profile.display_name,
            self.other.username,
        )

    def test_invalid_name_does_not_change_profile(self):
        self.client.force_login(self.owner)

        for name in ("   ", "a" * 226):
            response = self.client.post(
                reverse("user_profile:edit"),
                {"display_name": name, "bio": "Percobaan"},
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn(
                "display_name",
                response.context["form"].errors,
            )

            self.owner.profile.refresh_from_db()
            self.assertEqual(
                self.owner.profile.display_name,
                self.owner.username,
            )


class WardrobeEntryTests(TestCase):
    def test_guest_wardrobe_has_signin_prompt_without_private_profile(self):
        response = self.client.get(reverse("user_profile:wardrobe"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Every great find starts with a member.")
        self.assertContains(response, 'id="add-item-signin"')
        self.assertContains(response, "data-add-item-signin")
        self.assertContains(
            response,
            reverse("user_profile:login")
            + "?next="
            + reverse("clothing_catalog:create"),
        )
        self.assertNotContains(response, 'id="swapper-heading"')
        self.assertNotContains(response, "No clothing available to swap yet.")

    def test_signed_in_wardrobe_entry_opens_members_public_wardrobe(self):
        member = get_user_model().objects.create_user(username="wardrobe-entry")
        self.client.force_login(member)
        self.assertRedirects(
            self.client.get(reverse("user_profile:wardrobe")),
            reverse("user_profile:public", args=[member.username]),
        )
        response = self.client.get(
            reverse("user_profile:public", args=[member.username])
        )
        self.assertNotContains(response, 'id="add-item-signin"')
        self.assertNotContains(response, "data-add-item-signin")


class PublicProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = get_user_model().objects.create_user(
            username="public_member",
            email="private-address@example.com",
        )

        profile = cls.member.profile
        profile.display_name = "Nama Publik"
        profile.bio = "Suka pakaian vintage."
        profile.save()

    def public_url(self):
        return reverse(
            "user_profile:public",
            kwargs={"username": self.member.username},
        )

    def test_public_profile_can_be_opened_without_login(self):
        response = self.client.get(self.public_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nama Publik")
        self.assertContains(response, "Suka pakaian vintage.")
        self.assertNotContains(
            response,
            "private-address@example.com",
        )
        self.assertNotContains(
            response,
            reverse("user_profile:edit"),
        )

    def test_owner_sees_edit_link(self):
        self.client.force_login(self.member)

        response = self.client.get(self.public_url())

        self.assertContains(
            response,
            reverse("user_profile:edit"),
        )

    def test_inactive_account_is_not_public(self):
        self.member.is_active = False
        self.member.save()

        response = self.client.get(self.public_url())

        self.assertEqual(response.status_code, 404)

    def test_public_profile_does_not_accept_updates(self):
        response = self.client.post(
            self.public_url(),
            {"display_name": "Changed"},
        )

        self.assertEqual(response.status_code, 405)

        self.member.profile.refresh_from_db()
        self.assertEqual(
            self.member.profile.display_name,
            "Nama Publik",
        )

    def test_unknown_username_returns_404(self):
        response = self.client.get(
            reverse("user_profile:public", kwargs={"username": "missing_member"})
        )
        self.assertEqual(response.status_code, 404)

    def test_other_member_does_not_see_edit_link(self):
        other = get_user_model().objects.create_user(username="profile_visitor")
        self.client.force_login(other)
        response = self.client.get(self.public_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("user_profile:edit"))

    def test_username_lookup_supports_punctuation_unicode_and_numeric_names(self):
        for username in ("member.name+swap@example.com", "pengguna_é", "123"):
            with self.subTest(username=username):
                member = get_user_model().objects.create_user(username=username)
                response = self.client.get(
                    reverse("user_profile:public", kwargs={"username": username})
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["profile"].user_id, member.pk)

    def test_only_target_members_available_clothing_is_displayed(self):
        other = get_user_model().objects.create_user(username="other_clothing_owner")
        for owner, name, status in (
            (self.member, "Public available shirt", Clothing.Status.AVAILABLE),
            (self.member, "Private reserved shirt", Clothing.Status.RESERVED),
            (self.member, "Private swapped shirt", Clothing.Status.SWAPPED),
            (other, "Someone else's shirt", Clothing.Status.AVAILABLE),
        ):
            Clothing.objects.create(
                owner=owner,
                name=name,
                description="Test clothing",
                type=Clothing.Type.TOP,
                size=Clothing.Size.M,
                condition=Clothing.Condition.GOOD,
                status=status,
            )
        response = self.client.get(self.public_url())
        self.assertContains(response, "Public available shirt")
        self.assertNotContains(response, "Private reserved shirt")
        self.assertNotContains(response, "Private swapped shirt")
        self.assertNotContains(response, "Someone else's shirt")
        self.assertEqual(len(response.context["clothing_items"]), 1)

    def test_wardrobe_request_state_is_owner_only_and_uses_latest_pending_request(self):
        requester = get_user_model().objects.create_user(username="wardrobe_requester")
        details = {
            "name": "Wardrobe denim",
            "description": "A well-loved piece",
            "type": Clothing.Type.OUTERWEAR,
            "size": Clothing.Size.M,
            "condition": Clothing.Condition.GOOD,
        }
        requested = Clothing.objects.create(owner=self.member, **details)
        offered = Clothing.objects.create(owner=requester, **details)
        swaps = [
            SwapRequest.objects.create(
                requester=requester,
                requested_clothing=requested,
                offered_clothing=offered,
            )
            for _ in range(2)
        ]
        SwapRequest.objects.create(
            requester=requester,
            requested_clothing=requested,
            offered_clothing=offered,
            status=SwapRequest.Status.REJECTED,
        )
        self.client.force_login(self.member)
        response = self.client.get(self.public_url())
        self.assertTrue(response.context["is_owner"])
        self.assertEqual(
            response.context["clothing_items"][0].pending_request_id, swaps[-1].pk
        )
        self.assertContains(response, "Requested")
        self.assertContains(response, f'href="{swaps[-1].get_absolute_url()}"')
        self.assertNotContains(response, f'href="{swaps[0].get_absolute_url()}"')
        self.assertContains(response, reverse("clothing_catalog:my_list"))

        for visitor in (None, requester):
            if visitor:
                self.client.force_login(visitor)
            else:
                self.client.logout()
            response = self.client.get(self.public_url())
            self.assertFalse(response.context["is_owner"])
            self.assertContains(response, "Wardrobe denim")
            self.assertNotContains(response, "View Request")
            self.assertNotContains(response, swaps[-1].get_absolute_url())

    def test_empty_wardrobe_offers_owner_listing_and_visitor_discovery(self):
        self.client.force_login(self.member)
        response = self.client.get(self.public_url())
        self.assertContains(response, "My Wardrobe")
        self.assertContains(response, "List your first piece")
        self.assertContains(response, reverse("clothing_catalog:create"))
        self.client.logout()
        response = self.client.get(self.public_url())
        self.assertContains(response, "Explore other wardrobes")
        self.assertNotContains(response, "List your first piece")

    def test_private_profile_and_catalog_links_use_username(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("user_profile:detail"))
        self.assertContains(response, f'href="{self.public_url()}"')
        clothing = Clothing.objects.create(
            owner=self.member,
            name="Linked shirt",
            description="Test clothing",
            type=Clothing.Type.TOP,
            size=Clothing.Size.M,
            condition=Clothing.Condition.GOOD,
        )
        response = self.client.get(clothing.get_absolute_url())
        self.assertContains(response, f'href="{self.public_url()}"')

    def test_coordinates_are_not_exposed_on_public_profile(self):
        profile = self.member.profile
        profile.latitude = -6.123456789
        profile.longitude = 106.987654321
        profile.save()
        response = self.client.get(self.public_url())
        self.assertNotContains(response, "-6.123456789")
        self.assertNotContains(response, "106.987654321")


class ProfileLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="location_owner")
        cls.other = get_user_model().objects.create_user(username="location_other")
        cls.url = reverse("user_profile:location_edit")
        cls.data = {"district": "Beji", "city": "Depok", "province": "West Java"}

    def setUp(self):
        self.client.force_login(self.owner)

    def test_location_requires_login_for_read_and_write(self):
        self.client.logout()
        for method in (self.client.get, self.client.post):
            response = method(self.url)
            self.assertRedirects(
                response, reverse("user_profile:login") + "?next=" + self.url
            )

    def test_save_and_reopen_location(self):
        response = self.client.post(self.url, self.data, follow=True)
        self.assertContains(response, "Your location has been updated.")
        self.assertContains(response, "Depok, West Java")
        response = self.client.get(self.url)
        self.assertEqual(response.context["form"]["district"].value(), "Beji")
        self.assertEqual(response.context["form"]["city"].value(), "Depok")
        self.assertEqual(response.context["form"]["province"].value(), "West Java")

    def test_city_and_province_are_required_but_district_is_optional(self):
        response = self.client.post(self.url, {"city": "   ", "province": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("city", response.context["form"].errors)
        self.assertIn("province", response.context["form"].errors)
        self.owner.profile.refresh_from_db()
        self.assertFalse(self.owner.profile.city)
        response = self.client.post(self.url, {**self.data, "district": ""})
        self.assertRedirects(response, reverse("user_profile:detail"))

    def test_submitted_owner_and_unrelated_fields_are_ignored(self):
        profile = self.owner.profile
        profile.bio = "Original bio"
        profile.profile_picture = "image/upload/v1/profile-picture"
        profile.save()
        self.client.post(
            self.url + f"?user_id={self.other.pk}",
            {
                **self.data,
                "user": self.other.pk,
                "display_name": "Changed",
                "bio": "Changed",
                "profile_picture": "Changed",
                "latitude": "12.34",
                "longitude": "56.78",
            },
        )
        profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(profile.user_id, self.owner.pk)
        self.assertEqual(profile.display_name, self.owner.username)
        self.assertEqual(profile.bio, "Original bio")
        self.assertEqual(profile.profile_picture.public_id, "profile-picture")
        self.assertIsNone(profile.latitude)
        self.assertIsNone(profile.longitude)
        self.assertFalse(self.other.profile.city)

    def test_changing_manual_area_clears_stale_coordinates(self):
        profile = self.owner.profile
        profile.latitude = -6.1
        profile.longitude = 106.8
        profile.save()
        self.client.post(self.url, self.data)
        profile.refresh_from_db()
        self.assertIsNone(profile.latitude)
        self.assertIsNone(profile.longitude)

    def test_location_form_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, self.data).status_code, 403)

    def test_profile_shows_location_link_and_empty_state(self):
        response = self.client.get(reverse("user_profile:detail"))
        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, "No location added yet.")


AREA = {
    "district": "Beji",
    "city": "Depok",
    "province": "West Java",
    "latitude": -6.36,
    "longitude": 106.83,
}
PAYLOAD = {"address": {"suburb": "Beji", "city": "Depok", "state": "West Java"}}


class GeocodingServiceTests(TestCase):
    def response(self, opener, payload):
        opener.return_value.__enter__.return_value.read.return_value = json.dumps(
            payload
        ).encode()

    @patch("apps.user_profile.geocoding.urlopen")
    def test_jakarta_province_level_city_is_mapped_to_province(self, opener):
        self.response(
            opener,
            {
                "address": {
                    "suburb": "Gambir",
                    "city_district": "Central Jakarta",
                    "city": "Special Capital Region of Jakarta",
                    "ISO3166-2-lvl4": "ID-JK",
                }
            },
        )
        result = reverse_geocode(-6.18, 106.83)
        self.assertEqual(result["district"], "Gambir")
        self.assertEqual(result["city"], "Central Jakarta")
        self.assertEqual(result["province"], "Special Capital Region of Jakarta")

    @patch("apps.user_profile.geocoding.urlopen")
    def test_lookup_rounds_coordinates_identifies_app_and_caches_result(self, opener):
        self.response(opener, PAYLOAD)
        result = reverse_geocode(-6.361234, 106.831234)
        self.assertEqual(result, AREA)
        self.assertEqual(reverse_geocode(-6.361235, 106.831235), AREA)
        opener.assert_called_once()
        request = opener.call_args.args[0]
        query = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(query["lat"], ["-6.36"])
        self.assertEqual(query["lon"], ["106.83"])
        self.assertEqual(query["zoom"], ["12"])
        self.assertIn("Swapify", request.get_header("User-agent"))
        self.assertEqual(opener.call_args.kwargs["timeout"], 5)

    @patch("apps.user_profile.geocoding.urlopen")
    def test_gate_throttles_different_users_and_locations_until_cooldown(self, opener):
        self.response(opener, PAYLOAD)
        reverse_geocode(-6.36, 106.83)
        with self.assertRaises(GeocodingBusy):
            reverse_geocode(-6.37, 106.83)
        opener.assert_called_once()
        GeocodingCacheEntry.objects.filter(pk=GATE_KEY).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        reverse_geocode(-6.37, 106.83)
        self.assertEqual(opener.call_count, 2)

    @patch("apps.user_profile.geocoding.urlopen")
    def test_provider_failure_is_safe_and_does_not_cache_a_result(self, opener):
        for error in (TimeoutError(), URLError("private network detail")):
            with self.subTest(error=type(error).__name__):
                GeocodingCacheEntry.objects.all().delete()
                opener.side_effect = error
                with self.assertRaises(GeocodingError) as raised:
                    reverse_geocode(-6.36, 106.83)
                self.assertNotIn("private network detail", str(raised.exception))
                self.assertEqual(GeocodingCacheEntry.objects.count(), 1)

    @patch("apps.user_profile.geocoding.urlopen")
    def test_upstream_429_applies_a_shared_one_minute_backoff(self, opener):
        opener.side_effect = HTTPError("https://example.com", 429, "Busy", {}, None)
        with self.assertRaises(GeocodingError):
            reverse_geocode(-6.36, 106.83)
        gate = GeocodingCacheEntry.objects.get(pk=GATE_KEY)
        self.assertGreater(gate.expires_at, timezone.now() + timedelta(seconds=58))
        with self.assertRaises(GeocodingBusy):
            reverse_geocode(-6.37, 106.83)
        opener.assert_called_once()

    @patch("apps.user_profile.geocoding.urlopen")
    def test_incomplete_or_invalid_responses_are_not_cached(self, opener):
        for payload in ({"address": {}}, {"error": "Unable to geocode"}, []):
            with self.subTest(payload=payload):
                GeocodingCacheEntry.objects.all().delete()
                self.response(opener, payload)
                with self.assertRaises(AreaNotFound):
                    reverse_geocode(-6.36, 106.83)
                self.assertEqual(GeocodingCacheEntry.objects.count(), 1)
        GeocodingCacheEntry.objects.all().delete()
        opener.return_value.__enter__.return_value.read.return_value = b"not json"
        with self.assertRaises(GeocodingError):
            reverse_geocode(-6.36, 106.83)

    @patch("apps.user_profile.geocoding.urlopen")
    def test_expired_cache_is_refreshed_and_city_fallbacks_work(self, opener):
        self.response(opener, PAYLOAD)
        reverse_geocode(-6.36, 106.83)
        GeocodingCacheEntry.objects.all().update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        self.response(
            opener,
            {
                "address": {
                    "district": "Beji",
                    "county": "Depok",
                    "province": "West Java",
                }
            },
        )
        self.assertEqual(reverse_geocode(-6.36, 106.83), AREA)
        self.assertEqual(opener.call_count, 2)

    @patch("apps.user_profile.geocoding.urlopen")
    def test_non_rate_limit_http_failure_uses_normal_cooldown(self, opener):
        opener.side_effect = HTTPError("https://example.com", 503, "Down", {}, None)
        with self.assertRaises(GeocodingError):
            reverse_geocode(-6.36, 106.83)
        gate = GeocodingCacheEntry.objects.get(pk=GATE_KEY)
        self.assertGreater(gate.expires_at, timezone.now())
        self.assertLess(gate.expires_at, timezone.now() + timedelta(seconds=3))
        self.assertEqual(GeocodingCacheEntry.objects.count(), 1)


class DetectedLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="detected_owner")
        cls.other = get_user_model().objects.create_user(username="detected_other")
        cls.resolve_url = reverse("user_profile:location_resolve")
        cls.save_url = reverse("user_profile:location_edit")

    def setUp(self):
        self.client.force_login(self.user)

    def token(self, user=None):
        return signing.dumps(
            {**AREA, "user_id": (user or self.user).pk}, salt="user_profile.location"
        )

    def save_data(self, token):
        return {**AREA, "location_token": token}

    @patch("apps.user_profile.views.reverse_geocode", return_value=AREA)
    def test_resolve_previews_without_saving_then_confirmation_saves(self, lookup):
        response = self.client.post(
            self.resolve_url,
            {
                "latitude": -6.36,
                "longitude": 106.83,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        result = response.json()
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.city)
        self.assertNotIn("latitude", result)
        response = self.client.post(self.save_url, result)
        self.assertRedirects(response, reverse("user_profile:detail"))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, "Depok")
        self.assertEqual(self.user.profile.latitude, -6.36)
        self.assertEqual(self.user.profile.longitude, 106.83)
        public = self.client.get(
            reverse("user_profile:public", args=[self.user.username])
        )
        self.assertContains(public, "Depok, West Java")
        self.assertNotContains(public, "-6.36")
        self.assertNotContains(public, "106.83")

    @patch("apps.user_profile.views.reverse_geocode")
    def test_invalid_and_nonfinite_coordinates_do_not_contact_provider(self, lookup):
        for lat, lon in ((91, 0), (0, -181), ("nan", 0), (0, "inf"), ("", 1)):
            with self.subTest(lat=lat, lon=lon):
                response = self.client.post(
                    self.resolve_url,
                    {
                        "latitude": lat,
                        "longitude": lon,
                    },
                )
                self.assertEqual(response.status_code, 400)
        lookup.assert_not_called()

    def test_resolve_requires_authentication_post_and_csrf(self):
        self.assertEqual(self.client.get(self.resolve_url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.resolve_url, {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.resolve_url, {}).status_code, 302)

    def test_changed_area_drops_detected_coordinates_and_raw_coordinates_are_ignored(
        self,
    ):
        data = {**self.save_data(self.token()), "city": "Jakarta", "latitude": 85}
        response = self.client.post(self.save_url, data)
        self.assertEqual(response.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, "Jakarta")
        self.assertIsNone(self.user.profile.latitude)

    def test_foreign_tampered_and_expired_tokens_cannot_save_coordinates(self):
        old_time = time.time() - 3600
        with patch("django.core.signing.time.time", return_value=old_time):
            expired = self.token()
        for token in (self.token(self.other), self.token() + "tampered", expired):
            with self.subTest(token=token[-10:]):
                response = self.client.post(self.save_url, self.save_data(token))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].non_field_errors())
                self.user.profile.refresh_from_db()
                self.assertFalse(self.user.profile.city)

    @patch("apps.user_profile.views.reverse_geocode")
    def test_busy_and_unavailable_errors_are_returned_as_json(self, lookup):
        for error, status in (
            (GeocodingBusy("Try again shortly."), 429),
            (GeocodingError("Unavailable."), 503),
        ):
            lookup.side_effect = error
            response = self.client.post(
                self.resolve_url,
                {
                    "latitude": -6.36,
                    "longitude": 106.83,
                },
            )
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["error"], str(error))


class ProfilePhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="photo_owner")
        cls.other = get_user_model().objects.create_user(username="photo_other")
        profile = cls.owner.profile
        profile.bio = "Original bio"
        profile.profile_picture = CloudinaryImage("original-photo", version=1)
        profile.save()

    def setUp(self):
        self.client.force_login(self.owner)
        self.url = reverse("user_profile:edit")
        self.data = {"display_name": "New name", "bio": "New bio"}

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_uploaded_photo_belongs_to_authenticated_user_and_is_public(self, upload):
        upload.return_value = CloudinaryImage("new-photo", version=2)
        response = self.client.post(
            self.url,
            {
                **self.data,
                "new_profile_picture": image_upload(),
                "user": self.other.pk,
                "profile_picture": "forged-photo",
            },
            follow=True,
        )
        self.assertContains(response, "Your profile has been updated.")
        self.owner.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.profile_picture.public_id, "new-photo")
        self.assertEqual(self.other.profile.display_name, self.other.username)
        self.assertEqual(upload.call_args.kwargs["user_id"], self.owner.pk)
        public = self.client.get(
            reverse("user_profile:public", args=[self.owner.username])
        )
        self.assertContains(public, self.owner.profile.profile_picture.url)

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_no_new_upload_preserves_existing_photo(self, upload):
        self.assertRedirects(
            self.client.post(self.url, self.data), reverse("user_profile:detail")
        )
        upload.assert_not_called()
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.profile_picture.public_id, "original-photo")

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_failed_upload_preserves_photo_and_other_profile_fields(self, upload):
        upload.side_effect = ProfilePhotoUploadError("Please try again later.")
        response = self.client.post(
            self.url,
            {
                **self.data,
                "new_profile_picture": image_upload(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("new_profile_picture", response.context["form"].errors)
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.display_name, self.owner.username)
        self.assertEqual(self.owner.profile.bio, "Original bio")
        self.assertEqual(self.owner.profile.profile_picture.public_id, "original-photo")

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_supported_image_formats_and_size_boundary(self, upload):
        upload.return_value = CloudinaryImage("valid-photo", version=1)
        for image in (
            image_upload("PNG"),
            image_upload("JPEG"),
            image_upload("WEBP"),
            image_upload(byte_size=MAX_IMAGE_BYTES),
        ):
            with self.subTest(name=image.name, size=image.size):
                response = self.client.post(
                    self.url,
                    {
                        **self.data,
                        "new_profile_picture": image,
                    },
                )
                self.assertEqual(response.status_code, 302)
        self.assertEqual(upload.call_count, 4)

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_invalid_unsupported_and_oversized_images_never_upload(self, upload):
        for image in (
            SimpleUploadedFile("fake.png", b"invalid"),
            image_upload("GIF"),
            image_upload(byte_size=MAX_IMAGE_BYTES + 1),
        ):
            with self.subTest(name=image.name, size=image.size):
                response = self.client.post(
                    self.url,
                    {
                        **self.data,
                        "new_profile_picture": image,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("new_profile_picture", response.context["form"].errors)
        upload.assert_not_called()

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_photo_changes_require_csrf(self, upload):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, self.data).status_code, 403)
        upload.assert_not_called()


class ImageUploadServiceTests(TestCase):
    def setUp(self):
        config = patch(
            "common.images.cloudinary.config",
            return_value=SimpleNamespace(
                cloud_name="test-cloud",
                api_key="test-key",
                api_secret="test-secret",
            ),
        )
        self.config = config.start()
        self.addCleanup(config.stop)

    @patch("common.images.uploader.upload_image")
    def test_missing_credentials_fail_without_contacting_provider(self, upload):
        for key in ("cloud_name", "api_key", "api_secret"):
            config = {"cloud_name": "cloud", "api_key": "key", "api_secret": "secret"}
            config[key] = ""
            self.config.return_value = SimpleNamespace(**config)
            with self.assertRaises(ImageUploadError):
                upload_image(image_upload(), folder="test")
        upload.assert_not_called()

    @patch("common.images.uploader.upload_image")
    def test_file_is_rewound_and_uploaded_with_bounded_timeout(self, upload):
        image = image_upload()
        image.read()
        resource = CloudinaryImage("result", version=1)

        def receive_image(file, **options):
            self.assertEqual(file.tell(), 0)
            self.assertEqual(options["folder"], "swapify/profile-pictures/1")
            self.assertEqual(options["timeout"], 30)
            self.assertFalse(options["overwrite"])
            return resource

        upload.side_effect = receive_image
        self.assertIs(
            upload_image(image, folder="swapify/profile-pictures/1"), resource
        )

    @patch("common.images.uploader.upload_image")
    def test_provider_failures_do_not_expose_credentials_in_logs_or_errors(
        self, upload
    ):
        for error in (
            AuthorizationRequired("PRIVATE-CREDENTIAL"),
            NotAllowed("PRIVATE-CREDENTIAL"),
            CloudinaryError("PRIVATE-CREDENTIAL"),
        ):
            with self.subTest(error=type(error).__name__):
                upload.side_effect = error
                with self.assertLogs("common.images", level="WARNING") as logs:
                    with self.assertRaises(ImageUploadError) as raised:
                        upload_image(image_upload(), folder="test")
                self.assertNotIn("PRIVATE-CREDENTIAL", str(raised.exception))
                self.assertNotIn("PRIVATE-CREDENTIAL", str(logs.output))

    @patch("apps.user_profile.services.upload_image")
    def test_profile_wrapper_selects_folder_and_returns_uploaded_resource(self, upload):
        resource = CloudinaryImage("profile-result", version=1)
        upload.return_value = resource
        image = image_upload()
        self.assertIs(upload_profile_picture(image, user_id=42), resource)
        upload.assert_called_once_with(image, folder="swapify/profile-pictures/42")

    @patch("apps.user_profile.services.upload_image")
    def test_profile_wrapper_translates_upload_errors(self, upload):
        upload.side_effect = ImageUploadError("Temporarily unavailable.")
        with self.assertRaisesMessage(
            ProfilePhotoUploadError, "Temporarily unavailable."
        ):
            upload_profile_picture(image_upload(), user_id=42)


class LocationFormBoundaryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="location_boundary")
        self.profile = self.user.profile
        self.profile.district = "Beji"
        self.profile.city = "Depok"
        self.profile.province = "West Java"
        self.profile.latitude = -6.36
        self.profile.longitude = 106.83
        self.profile.save()
        self.data = {"district": "Beji", "city": "Depok", "province": "West Java"}

    def test_unchanged_manual_area_preserves_existing_coordinates(self):
        form = ProfileLocationForm(
            self.data, instance=self.profile, user_id=self.user.pk
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.latitude, -6.36)
        self.assertEqual(self.profile.longitude, 106.83)

    def test_commit_false_does_not_write_changes_to_database(self):
        form = ProfileLocationForm(
            {**self.data, "city": "Bogor"}, instance=self.profile, user_id=self.user.pk
        )
        self.assertTrue(form.is_valid(), form.errors)
        result = form.save(commit=False)
        self.assertEqual(result.city, "Bogor")
        self.assertIsNone(result.latitude)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.city, "Depok")
        self.assertEqual(self.profile.latitude, -6.36)

    def test_profile_string_uses_display_name(self):
        self.assertEqual(str(self.profile), self.user.username)

    def test_public_profile_lookup_honors_an_explicit_queryset(self):
        view = PublicProfileDetailView()
        view.kwargs = {"username": self.user.username}
        queryset = Profile.objects.filter(user=self.user)
        self.assertEqual(view.get_object(queryset=queryset), self.profile)
        with self.assertRaises(Http404):
            view.get_object(queryset=queryset.exclude(user=self.user))


class ProfileReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = get_user_model().objects.create_user(username="rated_member")
        cls.author = get_user_model().objects.create_user(username="rating_author")
        cls.other = get_user_model().objects.create_user(username="different_recipient")
        cls.url = reverse("user_profile:public", args=[cls.member.username])

    def add_review(self, rating=5, comment="", recipient=None, author=None):
        recipient = recipient or self.member
        author = author or self.author
        data = {
            "name": "Review fixture shirt",
            "description": "Good condition",
            "type": "top",
            "size": "M",
            "condition": "good",
            "status": Clothing.Status.SWAPPED,
        }
        requested = Clothing.objects.create(owner=recipient, **data)
        offered = Clothing.objects.create(owner=author, **data)
        swap = SwapRequest.objects.create(
            requester=author,
            requested_clothing=requested,
            offered_clothing=offered,
            status=SwapRequest.Status.ACCEPTED,
        )
        exchange = Transaction.objects.create(
            swap_request=swap,
            status=Transaction.Status.COMPLETED,
            meetup_date=timezone.now(),
            meetup_location="Private meetup",
            requester_received=True,
            owner_received=True,
            completed_at=timezone.now(),
        )
        return Review.objects.create(
            transaction=exchange,
            author=author,
            recipient=recipient,
            rating=rating,
            comment=comment,
        )

    def test_empty_profile_has_no_fabricated_rating(self):
        response = self.client.get(self.url)
        self.assertContains(response, "No reviews yet.")
        self.assertContains(
            response, "Reviews will appear here after completed exchanges."
        )
        self.assertEqual(
            response.context["rating_summary"], {"average": None, "count": 0}
        )
        self.assertEqual(list(response.context["reviews_page"]), [])
        self.assertNotContains(response, "0.0 / 5")

    def test_summary_only_includes_received_reviews_for_this_profile(self):
        self.add_review(rating=4, comment="First received review")
        self.add_review(rating=5, comment="Second received review")
        self.add_review(rating=1, recipient=self.other, comment="Another recipient")
        self.add_review(
            rating=2,
            author=self.member,
            recipient=self.other,
            comment="Written by this member",
        )
        response = self.client.get(self.url)
        self.assertEqual(
            response.context["rating_summary"], {"average": 4.5, "count": 2}
        )
        self.assertContains(response, "4.5 / 5")
        self.assertContains(response, "First received review")
        self.assertContains(response, "Second received review")
        self.assertNotContains(response, "Another recipient")
        self.assertNotContains(response, "Written by this member")

    def test_public_reviews_escape_comments_and_do_not_expose_transaction(self):
        review = self.add_review(comment="<script>alert('unsafe')</script>")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")
        self.assertContains(
            response, reverse("user_profile:public", args=[self.author.username])
        )
        self.assertNotContains(response, "Private meetup")
        self.assertNotContains(
            response, reverse("transaction_detail", args=[review.transaction_id])
        )

    def test_optional_comment_and_review_count_are_displayed(self):
        self.add_review()
        response = self.client.get(self.url)
        self.assertContains(response, "No written comment.")
        self.assertEqual(response.context["rating_summary"]["count"], 1)

    def test_pagination_is_newest_first_with_summary_over_all_reviews(self):
        reviews = [
            self.add_review(
                rating=1 if index == 0 else 5, comment=f"Review item {index}"
            )
            for index in range(11)
        ]
        # Identical timestamps must still produce stable pagination via the primary key.
        Review.objects.all().update(created_at=timezone.now())
        first = self.client.get(self.url)
        self.assertEqual(len(first.context["reviews_page"]), 10)
        self.assertEqual(
            [review.pk for review in first.context["reviews_page"]],
            [review.pk for review in reversed(reviews[1:])],
        )
        self.assertContains(first, "?reviews_page=2#reviews")
        second = self.client.get(self.url, {"reviews_page": 2})
        self.assertEqual(
            [review.pk for review in second.context["reviews_page"]], [reviews[0].pk]
        )
        self.assertEqual(second.context["rating_summary"]["count"], 11)
        self.assertAlmostEqual(second.context["rating_summary"]["average"], 51 / 11)
        self.assertEqual(
            first.context["rating_summary"], second.context["rating_summary"]
        )
        self.assertContains(second, "?reviews_page=1#reviews")

        for value, expected_page in (("invalid", 1), ("999", 2), ("-1", 2)):
            with self.subTest(page=value):
                response = self.client.get(self.url, {"reviews_page": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["reviews_page"].number, expected_page)

    def test_private_dashboard_uses_received_reviews_and_own_email(self):
        self.member.email = "owner-private@example.com"
        self.member.save()
        latest = self.add_review(rating=4, comment="A thoughtful swap.")
        self.add_review(rating=1, recipient=self.other, comment="Another member only")
        self.client.force_login(self.member)
        response = self.client.get(reverse("user_profile:detail"))
        self.assertEqual(response.context["latest_review"], latest)
        self.assertEqual(
            response.context["rating_summary"], {"average": 4.0, "count": 1}
        )
        self.assertContains(response, "owner-private@example.com")
        self.assertContains(response, "A thoughtful swap.")
        self.assertNotContains(response, "Another member only")
        self.assertNotContains(self.client.get(self.url), "owner-private@example.com")

    def test_private_reviews_filter_keeps_overall_summary_and_member_scope(self):
        self.add_review(rating=5, comment="Five star received")
        self.add_review(rating=2, comment="Two star received")
        self.add_review(rating=5, recipient=self.other, comment="Another recipient")
        self.client.force_login(self.member)
        url = reverse("user_profile:reviews")
        response = self.client.get(url, {"rating": "5"})
        self.assertEqual(
            response.context["rating_summary"], {"average": 3.5, "count": 2}
        )
        self.assertContains(response, "Five star received")
        self.assertNotContains(response, "Two star received")
        self.assertNotContains(response, "Another recipient")
        fragment = self.client.get(url, {"rating": "2"}, HTTP_X_PROFILE_REVIEWS="1")
        self.assertIn("Two star received", fragment.json()["html"])
        self.assertNotIn("Five star received", fragment.json()["html"])
        self.assertIn("X-Profile-Reviews", fragment.headers["Vary"])
        empty = self.client.get(url, {"rating": "1"})
        self.assertContains(empty, "No 1-star reviews yet.")
        invalid = self.client.get(url, {"rating": "invalid"})
        self.assertEqual(len(invalid.context["reviews"]), 2)

    def test_private_reviews_paginate_and_require_signin(self):
        url = reverse("user_profile:reviews")
        self.assertEqual(self.client.get(url).status_code, 302)
        for index in range(11):
            self.add_review(rating=5, comment=f"Received review {index}")
        self.client.force_login(self.member)
        response = self.client.get(url, {"rating": "5"})
        self.assertEqual(len(response.context["reviews"]), 10)
        self.assertContains(response, "rating=5&amp;page=2")
        last = self.client.get(url, {"rating": "5", "page": "2"})
        self.assertEqual(len(last.context["reviews"]), 1)


class ProfileDialogTests(TestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="profile-editor")
        self.other = get_user_model().objects.create_user(username="other-profile")
        self.client.force_login(self.member)

    def test_preferences_save_clear_and_reject_unknown_values_without_onboarding(self):
        url = reverse("user_profile:preferences_edit")
        response = self.client.post(
            url,
            {"preferences": ["tops", "shoes"], "user_id": self.other.pk},
            HTTP_X_PROFILE_DIALOG="1",
        )
        self.assertEqual(response.json(), {"redirect": reverse("user_profile:detail")})
        self.member.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(self.member.profile.preferences, ["tops", "shoes"])
        self.assertFalse(self.member.profile.onboarding_completed)
        self.assertEqual(self.other.profile.preferences, [])
        invalid = self.client.post(
            url, {"preferences": ["unknown"]}, HTTP_X_PROFILE_DIALOG="1"
        )
        self.assertEqual(invalid.status_code, 422)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.preferences, ["tops", "shoes"])
        self.client.post(url, {}, HTTP_X_PROFILE_DIALOG="1")
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.preferences, [])

    def test_dialog_forms_are_fragments_and_full_pages_are_fallbacks(self):
        for name in ("edit", "preferences_edit", "location_edit"):
            url = reverse(f"user_profile:{name}")
            fragment = self.client.get(url, HTTP_X_PROFILE_DIALOG="1")
            self.assertEqual(fragment.status_code, 200)
            self.assertContains(fragment, "data-profile-form")
            self.assertNotContains(fragment, "<html")
            self.assertIn("X-Profile-Dialog", fragment.headers["Vary"])
            self.assertContains(self.client.get(url), "<html")
        invalid = self.client.post(
            reverse("user_profile:edit"),
            {"display_name": ""},
            HTTP_X_PROFILE_DIALOG="1",
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertNotContains(invalid, "<html", status_code=422)
        success = self.client.post(
            reverse("user_profile:edit"),
            {"display_name": "Edited name", "bio": "Changed bio"},
            HTTP_X_PROFILE_DIALOG="1",
        )
        self.assertEqual(success.status_code, 200)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.display_name, "Edited name")

    def test_preferences_require_authentication_and_csrf(self):
        url = reverse("user_profile:preferences_edit")
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.member)
        self.assertEqual(
            protected.post(url, {"preferences": ["tops"]}).status_code, 403
        )
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(
            self.client.post(url, {"preferences": ["tops"]}).status_code, 302
        )


class OnboardingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="onboarding_member",
            password=PASSWORD,
        )
        cls.other = get_user_model().objects.create_user(username="other_onboarding")

    def setUp(self):
        self.url = reverse("user_profile:onboarding")
        self.client.force_login(self.user)

    def post_step(self, step, **data):
        return self.client.post(
            self.url,
            {"step": step, **data},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_setup_requires_authentication_and_csrf(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(self.url, {"step": 3}).status_code, 403)

    def test_each_step_saves_only_current_members_fields(self):
        response = self.post_step(
            1,
            display_name="Alex",
            bio="I love vintage pieces.",
            user_id=self.other.pk,
            preferences=["shoes"],
        )
        self.assertEqual(response.json()["step"], 2)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.display_name, "Alex")
        self.assertEqual(self.user.profile.preferences, [])
        self.other.profile.refresh_from_db()
        self.assertEqual(self.other.profile.display_name, self.other.username)
        response = self.post_step(
            2,
            district="Gambir",
            city="Central Jakarta",
            province="Jakarta",
            location_agreement="on",
        )
        self.assertEqual(response.json()["step"], 3)
        response = self.post_step(3, preferences=["tops", "shoes"])
        self.assertEqual(response.json()["step"], 4)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, "Central Jakarta")
        self.assertEqual(self.user.profile.preferences, ["tops", "shoes"])
        self.assertTrue(self.user.profile.onboarding_completed)
        response = self.client.get(self.url + "?step=3")
        self.assertContains(response, 'value="tops" class="sr-only" checked')

    def test_invalid_step_and_preferences_do_not_write(self):
        for step in ("oops", 0, 4):
            self.assertEqual(self.post_step(step).status_code, 400)
        response = self.post_step(3, preferences=["arbitrary-value"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("preferences", response.json()["errors"])
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.preferences, [])
        self.assertFalse(self.user.profile.onboarding_completed)

    def test_profile_and_location_validation(self):
        response = self.post_step(1, display_name="Alex", bio="x" * 1001)
        self.assertIn("bio", response.json()["errors"])
        response = self.post_step(2, city="Jakarta", province="Jakarta")
        self.assertIn("location_agreement", response.json()["errors"])
        response = self.post_step(2, location_agreement="on")
        self.assertIn("city", response.json()["errors"])

    def test_optional_preferences_can_be_empty_and_changed(self):
        self.post_step(3, preferences=["tops"])
        self.assertEqual(self.post_step(3).status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.preferences, [])

    def test_invalid_photo_and_upload_failure_preserve_profile(self):
        response = self.post_step(
            1,
            display_name="Changed",
            new_profile_picture=SimpleUploadedFile(
                "fake.png",
                b"not-an-image",
                content_type="image/png",
            ),
        )
        self.assertIn("new_profile_picture", response.json()["errors"])
        with patch("apps.user_profile.views.upload_profile_picture") as upload:
            upload.side_effect = ProfilePhotoUploadError("Upload unavailable.")
            response = self.post_step(
                1,
                display_name="Changed",
                new_profile_picture=image_upload(),
            )
        self.assertEqual(response.status_code, 400)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.display_name, self.user.username)

    def test_finish_later_preserves_saved_progress(self):
        self.post_step(1, display_name="Saved name", bio="Saved bio")
        self.assertRedirects(
            self.client.post(self.url, {"action": "later"}),
            reverse("clothing_catalog:list"),
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Saved bio")
        self.assertFalse(self.user.profile.onboarding_completed)

    def test_non_javascript_submission_redirects_and_errors_render(self):
        response = self.client.post(self.url, {"step": 1, "display_name": "Alex"})
        self.assertRedirects(response, self.url + "?step=2")
        response = self.client.post(self.url, {"step": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["step"], 2)
        self.assertTrue(response.context["location_form"].errors)

    def test_registration_requires_name_and_community_agreement(self):
        self.client.logout()
        response = self.client.post(
            reverse("user_profile:register"),
            {
                "username": "missing_details",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertIn("name", response.context["form"].errors)
        self.assertIn("community_agreement", response.context["form"].errors)

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_photo_autosaves_without_submitting_other_profile_fields(self, upload):
        upload.return_value = CloudinaryImage("swapify/profile-pictures/saved-photo")
        response = self.client.post(
            self.url,
            {
                "action": "upload_photo",
                "new_profile_picture": image_upload(),
                "display_name": "Do not change this",
                "user_id": self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("saved-photo", response.json()["profile_picture_url"])
        self.user.profile.refresh_from_db()
        self.assertIn("saved-photo", str(self.user.profile.profile_picture))
        self.assertEqual(self.user.profile.display_name, self.user.username)
        self.other.profile.refresh_from_db()
        self.assertFalse(self.other.profile.profile_picture)
        # The following Next request must keep the autosaved photo.
        self.post_step(1, display_name="Alex")
        self.user.profile.refresh_from_db()
        self.assertIn("saved-photo", str(self.user.profile.profile_picture))
        self.assertEqual(upload.call_count, 1)

    @patch("apps.user_profile.views.upload_profile_picture")
    def test_photo_autosave_rejects_invalid_images_and_handles_upload_failure(
        self, upload
    ):
        for data in (
            {},
            {"new_profile_picture": SimpleUploadedFile("bad.png", b"bad")},
        ):
            response = self.client.post(self.url, {"action": "upload_photo", **data})
            self.assertEqual(response.status_code, 400)
            self.assertIn("new_profile_picture", response.json()["errors"])
        upload.assert_not_called()
        upload.side_effect = ProfilePhotoUploadError("Upload unavailable.")
        response = self.client.post(
            self.url,
            {
                "action": "upload_photo",
                "new_profile_picture": image_upload(),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Upload unavailable.")
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.profile_picture)
