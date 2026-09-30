from django.urls import path

from .views import MyProfileDetailView

app_name = "user_profile"

urlpatterns = [path("", MyProfileDetailView.as_view(), name="detail")]
