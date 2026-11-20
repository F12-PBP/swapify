from django.contrib.auth import get_user_model
from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import (
    PermissionDenied as DRFPermissionDenied,
)
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.transaction.models import Transaction

from .models import Review
from .serializers import (
    PublicReviewSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
)
from .services import submit_review


class UserReviewListAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, username):
        user = get_object_or_404(
            get_user_model(),
            username=username,
            is_active=True,
        )

        reviews = Review.objects.filter(recipient=user).select_related(
            "author", "recipient", "transaction"
        )

        serializer = PublicReviewSerializer(reviews, many=True)

        return Response(serializer.data)


class ReviewCreateAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_transaction(self, request, transaction_id):
        exchange = get_object_or_404(
            Transaction.objects.select_related(
                "swap_request__requester", "swap_request__requested_clothing__owner"
            ),
            pk=transaction_id,
        )
        if not exchange.is_participant(request.user):
            raise DRFPermissionDenied("Only exchange participants can view reviews.")
        return exchange

    def get(self, request, transaction_id):
        exchange = self.get_transaction(request, transaction_id)
        reviews = exchange.reviews.select_related("author", "recipient", "transaction")
        return Response(ReviewSerializer(reviews, many=True).data)

    def post(self, request, transaction_id):
        self.get_transaction(request, transaction_id)
        input_serializer = ReviewCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        try:
            review = submit_review(
                transaction_id=transaction_id,
                author=request.user,
                **input_serializer.validated_data,
            )
        except Transaction.DoesNotExist:
            return Response(
                {"detail": "Transaction not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoPermissionDenied as error:
            raise DRFPermissionDenied(str(error)) from error
        except DjangoValidationError as error:
            if hasattr(error, "message_dict"):
                raise DRFValidationError(error.message_dict) from error

            raise DRFValidationError({"detail": error.messages}) from error

        output_serializer = ReviewSerializer(review)

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )
