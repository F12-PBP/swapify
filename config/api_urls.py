from django.urls import include, path

urlpatterns = [
    path("", include("apps.clothing_catalog.api_urls")),
    path("", include("apps.user_profile.api_urls")),
    path("", include("apps.review_rating.api_urls")),
]
