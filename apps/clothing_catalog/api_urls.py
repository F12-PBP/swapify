from django.urls import path

from .api_views import (
    ClothingDetailAPIView,
    ClothingListCreateAPIView,
    MyClothingListAPIView,
)

app_name = "clothing_catalog_api"

urlpatterns = [
    path("clothing/", ClothingListCreateAPIView.as_view(), name="clothing-list"),
    path("clothing/me/", MyClothingListAPIView.as_view(), name="my-clothing-list"),
    path(
        "clothing/<uuid:uuid>/",
        ClothingDetailAPIView.as_view(),
        name="clothing-detail",
    ),
]
