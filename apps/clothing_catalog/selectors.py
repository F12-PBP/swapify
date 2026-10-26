"""Catalog queries shared by discovery and item detail pages."""

from django.db.models import Avg, OuterRef, Q, Subquery

from apps.review_rating.models import Review

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


def discover_listings(user, search=""):
    queryset = listings_with_owners().filter(status=Clothing.Status.AVAILABLE)
    if user.is_authenticated:
        queryset = queryset.exclude(owner=user)
    return catalog_search(queryset, search).order_by("-created_at", "-pk")
