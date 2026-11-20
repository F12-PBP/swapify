from django.urls import include, path

urlpatterns = [
    path("", include("apps.user_profile.api_urls")),
    path("", include("apps.review_rating.api_urls")),
    path("", include("apps.swap_request.api_urls")),
]
