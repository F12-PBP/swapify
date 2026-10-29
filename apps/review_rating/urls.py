from django.urls import path

from .views import ReviewCreateView

app_name = "review_rating"

urlpatterns = [
    path(
        "transaction/<uuid:transaction_id>/",
        ReviewCreateView.as_view(),
        name="create",
    ),
]
