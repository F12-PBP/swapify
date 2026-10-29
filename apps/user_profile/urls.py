from django.urls import path

from .views import (
    LocationResolveView,
    LoginUserView,
    LogoutUserView,
    MyProfileDetailView,
    MyProfileLocationUpdateView,
    MyProfilePreferencesUpdateView,
    MyProfileUpdateView,
    MyReviewListView,
    OnboardingView,
    PublicProfileDetailView,
    RegisterUserView,
    WardrobeView,
)

app_name = "user_profile"

urlpatterns = [
    path("", MyProfileDetailView.as_view(), name="detail"),
    path("wardrobe/", WardrobeView.as_view(), name="wardrobe"),
    path("login/", LoginUserView.as_view(), name="login"),
    path("register/", RegisterUserView.as_view(), name="register"),
    path("onboarding/", OnboardingView.as_view(), name="onboarding"),
    path("logout/", LogoutUserView.as_view(), name="logout"),
    path("edit/", MyProfileUpdateView.as_view(), name="edit"),
    path(
        "preferences/edit/",
        MyProfilePreferencesUpdateView.as_view(),
        name="preferences_edit",
    ),
    path("reviews/", MyReviewListView.as_view(), name="reviews"),
    path(
        "location/edit/",
        MyProfileLocationUpdateView.as_view(),
        name="location_edit",
    ),
    path("location/resolve/", LocationResolveView.as_view(), name="location_resolve"),
    path("users/<str:username>/", PublicProfileDetailView.as_view(), name="public"),
]
