from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clothing_catalog.models import Clothing
from apps.swap_request.models import SwapRequest
from apps.transaction.models import Transaction

from .models import Profile

PASSWORD = "Swapify-Check!2026-audit"


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="existing_member", password=PASSWORD
        )

    def register(self, **overrides):
        data = {
            "username": "new_member",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("user_profile:register"), data)

    def test_registration_creates_user_and_exactly_one_profile(self):
        response = self.register()
        self.assertRedirects(response, reverse("user_profile:login"))
        user = get_user_model().objects.get(username="new_member")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        self.assertEqual(user.profile.display_name, user.username)
        self.assertNotIn("_auth_user_id", self.client.session)

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
        historical_apps = (
            MigrationExecutor(connection)
            .loader.project_state([("user_profile", "0001_initial")])
            .apps
        )
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
                {"username": username, "password1": PASSWORD, "password2": PASSWORD},
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
