"""Catalog queries shared by discovery and item detail pages."""

import math

from django.db.models import (
    Avg,
    Case,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import ACos, Cos, Greatest, Least, Radians, Sin

from apps.review_rating.models import Review

from .categories import STYLE_TO_TYPE
from .models import Clothing


def catalog_search(queryset, search):
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    return queryset


def listings_with_owners():
    ratings = (
        Review.objects.filter(recipient_id=OuterRef("owner_id"))
        .order_by()
        .values("recipient_id")
        .annotate(average=Avg("rating"))
        .values("average")[:1]
    )
    return Clothing.objects.select_related("owner__profile").annotate(
        owner_rating=Subquery(ratings)
    )


def viewer_coordinates(user):
    if not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    if profile is None or profile.latitude is None or profile.longitude is None:
        return None
    lat, lon = profile.latitude, profile.longitude
    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and -90 <= lat <= 90
        and -180 <= lon <= 180
    ):
        return None
    return lat, lon


def with_distance(queryset, user):
    """Approximate owner-to-viewer distance; coordinates never leave the server."""
    coordinates = viewer_coordinates(user)
    if coordinates is None:
        return queryset
    lat, lon = coordinates
    cosine = Sin(Radians(Value(lat))) * Sin(
        Radians(F("owner__profile__latitude"))
    ) + Cos(Radians(Value(lat))) * Cos(Radians(F("owner__profile__latitude"))) * Cos(
        Radians(F("owner__profile__longitude")) - Radians(Value(lon))
    )
    valid_area = Q(
        owner__profile__latitude__range=(-90, 90),
        owner__profile__longitude__range=(-180, 180),
    )
    return queryset.annotate(
        distance_km=Case(
            When(
                valid_area,
                then=Value(6371.0)
                * ACos(Least(Value(1.0), Greatest(Value(-1.0), cosine))),
            ),
            default=Value(None),
            output_field=FloatField(),
        )
    )


def discover_listings(user, filters=None):
    filters = filters or {}
    queryset = listings_with_owners().filter(status=Clothing.Status.AVAILABLE)
    if user.is_authenticated:
        queryset = queryset.exclude(owner=user)
    return filter_listings(queryset, user, filters)


def member_listings(user, owner_id, filters=None):
    queryset = listings_with_owners().filter(
        owner_id=owner_id, status=Clothing.Status.AVAILABLE
    )
    return filter_listings(queryset, user, filters or {})


def filter_listings(queryset, user, filters):
    queryset = catalog_search(queryset, filters.get("search"))
    for field in ("type", "size", "condition"):
        if filters.get(field):
            queryset = queryset.filter(**{field: filters[field]})
    queryset = with_distance(queryset, user)
    if viewer_coordinates(user) and filters.get("distance"):
        queryset = queryset.filter(distance_km__lte=int(filters["distance"]))
    if viewer_coordinates(user) and filters.get("sort") == "nearest":
        return queryset.order_by(
            F("distance_km").asc(nulls_last=True), "-created_at", "-pk"
        )
    if (
        user.is_authenticated
        and (filters.get("sort") or "recommended") == "recommended"
    ):
        preferences = getattr(getattr(user, "profile", None), "preferences", [])
        preferred_types = [
            STYLE_TO_TYPE[style] for style in preferences if style in STYLE_TO_TYPE
        ]
        queryset = queryset.annotate(
            preference_rank=Case(
                When(type__in=preferred_types, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("preference_rank", "-created_at", "-pk")
    else:
        queryset = queryset.order_by("-created_at", "-pk")
    return queryset


def related_listings(user, clothing):
    """Prefer the same category, then fill from other available pieces."""
    return (
        discover_listings(user)
        .exclude(pk=clothing.pk)
        .annotate(
            related_rank=Case(
                When(type=clothing.type, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("related_rank", "-created_at", "-pk")[:4]
    )
