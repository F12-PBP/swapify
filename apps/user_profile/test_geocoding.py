import json
import time
from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .geocoding import (
    GATE_KEY,
    AreaNotFound,
    GeocodingBusy,
    GeocodingError,
    reverse_geocode,
)
from .models import GeocodingCacheEntry

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
