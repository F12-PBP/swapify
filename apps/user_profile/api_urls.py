from django.urls import path

from .api_views import (
    CsrfTokenAPIView,
    LoginAPIView,
    LogoutAPIView,
    MyProfileAPIView,
    PublicProfileAPIView,
)

app_name = "user_profile_api"

urlpatterns = [
    path("auth/csrf/", CsrfTokenAPIView.as_view(), name="csrf"),
    path("auth/login/", LoginAPIView.as_view(), name="login"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path("profile/me/", MyProfileAPIView.as_view(), name="my-profile"),
    path(
        "profiles/<str:username>/",
        PublicProfileAPIView.as_view(),
        name="public-profile",
    ),
]
