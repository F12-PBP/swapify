from django.urls import path

from .api_views import (
    CsrfTokenAPIView,
    LocationResolveAPIView,
    LoginAPIView,
    LogoutAPIView,
    MyProfileAPIView,
    OnboardingAPIView,
    ProfileLocationAPIView,
    ProfilePhotoAPIView,
    PublicProfileAPIView,
    RegisterAPIView,
)

app_name = "user_profile_api"

urlpatterns = [
    path("auth/csrf/", CsrfTokenAPIView.as_view(), name="csrf"),
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("profile/me/photo/", ProfilePhotoAPIView.as_view(), name="photo"),
    path("profile/me/location/", ProfileLocationAPIView.as_view(), name="location"),
    path(
        "locations/resolve/", LocationResolveAPIView.as_view(), name="location-resolve"
    ),
    path(
        "profile/me/onboarding/<int:step>/",
        OnboardingAPIView.as_view(),
        name="onboarding",
    ),
    path("auth/login/", LoginAPIView.as_view(), name="login"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path("profile/me/", MyProfileAPIView.as_view(), name="my-profile"),
    path(
        "profiles/<str:username>/",
        PublicProfileAPIView.as_view(),
        name="public-profile",
    ),
]
