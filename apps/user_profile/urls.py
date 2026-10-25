from django.urls import path

from .views import (
    LoginUserView,
    LogoutUserView,
    MyProfileDetailView,
    MyProfileUpdateView,
    PublicProfileDetailView,
    RegisterUserView,
)

app_name = "user_profile"

urlpatterns = [
    path("", MyProfileDetailView.as_view(), name="detail"),
    path("login/", LoginUserView.as_view(), name="login"),
    path("register/", RegisterUserView.as_view(), name="register"),
    path("logout/", LogoutUserView.as_view(), name="logout"),
    path("edit/", MyProfileUpdateView.as_view(), name="edit"),
    path("users/<str:username>/", PublicProfileDetailView.as_view(), name="public"),
]
