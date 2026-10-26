"""Catalog queries shared by discovery and item detail pages."""

from django.db.models import Avg, Case, IntegerField, OuterRef, Q, Subquery, Value, When

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


def discover_listings(user, filters=None):
    filters = filters or {}
    queryset = listings_with_owners().filter(status=Clothing.Status.AVAILABLE)
    if user.is_authenticated:
        queryset = queryset.exclude(owner=user)
    queryset = catalog_search(queryset, filters.get("search"))
    for field in ("type", "size", "condition"):
        if filters.get(field):
            queryset = queryset.filter(**{field: filters[field]})
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
