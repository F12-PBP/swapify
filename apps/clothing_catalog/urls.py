from django.urls import path

from .views import (
    ClothingCreateView,
    ClothingDeleteView,
    ClothingDetailView,
    ClothingListView,
    ClothingUpdateView,
    MyClothingListView,
)

app_name = "clothing_catalog"

urlpatterns = [
    path("", ClothingListView.as_view(), name="list"),
    path("my-clothes/", MyClothingListView.as_view(), name="my_list"),
    path("add/", ClothingCreateView.as_view(), name="create"),
    path("<int:pk>/", ClothingDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", ClothingUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", ClothingDeleteView.as_view(), name="delete"),
]
