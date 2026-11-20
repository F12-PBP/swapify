from django.urls import path

from .api_views import ReviewCreateAPIView, UserReviewListAPIView

app_name = "review_rating_api"

urlpatterns = [
    path(
        "profiles/<str:username>/reviews/",
        UserReviewListAPIView.as_view(),
        name="user-review-list",
    ),
    path(
        "transactions/<uuid:transaction_id>/reviews/",
        ReviewCreateAPIView.as_view(),
        name="review-create",
    ),
]
