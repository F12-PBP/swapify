import hashlib
import json
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import GeocodingCacheEntry

GATE_KEY = "nominatim:request-gate"


class GeocodingError(Exception):
    status_code = 503


class GeocodingBusy(GeocodingError):
    status_code = 429


class AreaNotFound(GeocodingError):
    status_code = 422


def _area_from_response(payload):
    address = payload.get("address") if isinstance(payload, dict) else None
    if not isinstance(address, dict):
        raise AreaNotFound("No area was found. Please enter your location manually.")

    def first(*keys):
        for key in keys:
            value = address.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:225]
        return ""

    area = {
        "district": first("city_district", "district", "suburb", "borough"),
        "city": first("city", "town", "municipality", "county"),
        "province": first("state", "province", "region"),
    }
    # Jakarta is a province-level city in OSM; its municipalities are districts.
    if address.get("ISO3166-2-lvl4") == "ID-JK" and not first("state", "province"):
        area = {
            "district": first("suburb", "district", "borough"),
            "city": first("city_district", "municipality", "city"),
            "province": first("city"),
        }
    if not area["city"] or not area["province"]:
        raise AreaNotFound(
            "We could not find a complete area. Please enter your location manually."
        )
    return area


def reverse_geocode(latitude, longitude):
    # Area-level precision avoids sending the browser's exact position upstream.
    latitude, longitude = round(latitude, 2), round(longitude, 2)
    endpoint = settings.NOMINATIM_BASE_URL.rstrip("/") + "/reverse"
    digest = hashlib.sha256(endpoint.encode()).hexdigest()[:16]
    cache_key = f"area:{digest}:{latitude:.2f}:{longitude:.2f}"
    now = timezone.now()
    cached = GeocodingCacheEntry.objects.filter(
        pk=cache_key, expires_at__gt=now
    ).first()
    if cached:
        return {**cached.value, "latitude": latitude, "longitude": longitude}

    # A conditional database update gives all workers one atomic request gate.
    GeocodingCacheEntry.objects.get_or_create(
        key=GATE_KEY, defaults={"expires_at": now}
    )
    claimed = GeocodingCacheEntry.objects.filter(
        pk=GATE_KEY, expires_at__lte=now
    ).update(expires_at=now + timedelta(seconds=30))
    if not claimed:
        raise GeocodingBusy("Location lookup is busy. Please try again shortly.")

    query = urlencode(
        {
            "lat": f"{latitude:.2f}",
            "lon": f"{longitude:.2f}",
            "format": "jsonv2",
            "addressdetails": 1,
            "zoom": 12,
            "accept-language": "en",
        }
    )
    request = Request(
        f"{endpoint}?{query}",
        headers={
            "User-Agent": settings.NOMINATIM_USER_AGENT,
            "Accept": "application/json",
        },
    )
    cooldown = 1.1
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read(65536))
    except HTTPError as error:
        if error.code == 429:
            cooldown = 60
        raise GeocodingError(
            "Location lookup is unavailable. "
            "Please try again later or enter your area manually."
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise GeocodingError(
            "Location lookup failed. Please try again or enter your area manually."
        ) from None
    finally:
        GeocodingCacheEntry.objects.filter(pk=GATE_KEY).update(
            expires_at=timezone.now() + timedelta(seconds=cooldown)
        )

    area = _area_from_response(payload)
    GeocodingCacheEntry.objects.update_or_create(
        key=cache_key,
        defaults={"value": area, "expires_at": now + timedelta(days=1)},
    )
    GeocodingCacheEntry.objects.filter(expires_at__lte=now).exclude(
        pk=GATE_KEY
    ).delete()
    return {**area, "latitude": latitude, "longitude": longitude}
