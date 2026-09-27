from django.urls import path

from .views import (
    ClothingCreateView,
    ClothingDeleteView,
    ClothingDetailView,
    ClothingListView,
    ClothingUpdateView,
)

app_name = "clothingCatalog"

urlpatterns = [
    path("", ClothingListView.as_view(), name="list"),
    path("add/", ClothingCreateView.as_view(), name="create"),
    path("<int:pk>/", ClothingDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", ClothingUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", ClothingDeleteView.as_view(), name="delete"),
]
