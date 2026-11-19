from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChatViewSet,
    ClothingViewSet,
    MobileLogoutView,
    MobileTokenView,
    ProfileView,
    ReviewViewSet,
    SwapRequestViewSet,
    TransactionViewSet,
)

router = DefaultRouter()
router.register("catalog", ClothingViewSet, basename="catalog")
router.register("swap-requests", SwapRequestViewSet, basename="swap-request")
router.register("transactions", TransactionViewSet, basename="transaction")
router.register("chats", ChatViewSet, basename="chat")
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path("auth/token/", MobileTokenView.as_view(), name="token"),
    path("auth/logout/", MobileLogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("", include(router.urls)),
]
