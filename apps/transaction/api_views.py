from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import (
    PermissionDenied,
)
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.swap_request.models import SwapRequest

from .models import Transaction
from .serializers import (
    TransactionDetailSerializer,
    TransactionUpdateSerializer,
)
from .services import (
    cancel_ready_transaction,
    confirm_receipt,
    start_transaction,
    unvalidate_resi,
    validate_resi,
)


class TransactionParticipantMixin:
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "transaction_id"

    def get_queryset(self):
        return Transaction.objects.select_related(
            "swap_request__requester__profile",
            "swap_request__requested_clothing__owner__profile",
            "swap_request__offered_clothing",
        ).filter(
            Q(swap_request__requester=self.request.user)
            | Q(swap_request__requested_clothing__owner=self.request.user)
        )


class TransactionDetailAPIView(
    TransactionParticipantMixin,
    generics.RetrieveAPIView,
):
    serializer_class = TransactionDetailSerializer


class TransactionUpdateAPIView(
    TransactionParticipantMixin,
    generics.UpdateAPIView,
):
    serializer_class = TransactionUpdateSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.method in ("PUT", "PATCH"):
            queryset = queryset.select_for_update(of=("self",))
        return queryset

    def get_object(self):
        exchange = super().get_object()
        if (
            exchange.status != Transaction.Status.WAITING
            or exchange.swap_request.status != SwapRequest.Status.ACCEPTED
        ):
            raise PermissionDenied("Exchange details are locked after it starts.")
        return exchange

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)


class TransactionStartAPIView(TransactionParticipantMixin, APIView):
    def post(self, request, transaction_id):
        exchange = get_object_or_404(self.get_queryset(), pk=transaction_id)
        try:
            exchange = start_transaction(exchange.pk, request.user)
        except DjangoValidationError as error:
            raise DRFValidationError({"error": error.messages})

        exchange = get_object_or_404(self.get_queryset(), pk=exchange.pk)
        message = (
            "Exchange started. Details are now locked."
            if exchange.status == Transaction.Status.IN_PROGRESS
            else "You are ready. Waiting for the other party to be ready."
        )
        serializer = TransactionDetailSerializer(
            exchange,
            context={"request": request},
        )
        return Response({"message": message, "transaction": serializer.data})


class TransactionCancelAPIView(TransactionParticipantMixin, APIView):
    def post(self, request, transaction_id):
        exchange = get_object_or_404(self.get_queryset(), pk=transaction_id)
        try:
            cancel_ready_transaction(exchange.pk, request.user)
        except DjangoValidationError as error:
            raise DRFValidationError({"error": error.messages})

        exchange = get_object_or_404(self.get_queryset(), pk=exchange.pk)
        serializer = TransactionDetailSerializer(
            exchange,
            context={"request": request},
        )
        return Response(
            {
                "message": (
                    "You have unreadied yourself. You can now change the details."
                ),
                "transaction": serializer.data,
            }
        )


class TransactionValidateResiAPIView(TransactionParticipantMixin, APIView):
    def post(self, request, transaction_id):
        exchange = get_object_or_404(self.get_queryset(), pk=transaction_id)
        try:
            validate_resi(exchange.pk, request.user)
        except DjangoValidationError as error:
            raise DRFValidationError({"error": error.messages})

        exchange = get_object_or_404(self.get_queryset(), pk=exchange.pk)
        serializer = TransactionDetailSerializer(
            exchange,
            context={"request": request},
        )
        return Response(
            {
                "message": (
                    "You have validated the other's resi. Waiting for the other to "
                    "validate yours before exchange can be started!"
                ),
                "transaction": serializer.data,
            }
        )


class TransactionUnvalidateResiAPIView(TransactionParticipantMixin, APIView):
    def post(self, request, transaction_id):
        exchange = get_object_or_404(self.get_queryset(), pk=transaction_id)
        try:
            unvalidate_resi(exchange.pk, request.user)
        except DjangoValidationError as error:
            raise DRFValidationError({"error": error.messages})

        exchange = get_object_or_404(self.get_queryset(), pk=exchange.pk)
        serializer = TransactionDetailSerializer(
            exchange,
            context={"request": request},
        )
        return Response(
            {
                "message": (
                    "You have unvalidated the other's resi. Please check thoroughly "
                    "before validating!"
                ),
                "transaction": serializer.data,
            }
        )


class TransactionReceivedAPIView(TransactionParticipantMixin, APIView):
    def post(self, request, transaction_id):
        exchange = get_object_or_404(self.get_queryset(), pk=transaction_id)
        try:
            exchange = confirm_receipt(exchange.pk, request.user)
        except DjangoValidationError as error:
            raise DRFValidationError({"error": error.messages})

        exchange = get_object_or_404(self.get_queryset(), pk=exchange.pk)
        message = (
            "Exchange completed. Both items are swapped."
            if exchange.status == Transaction.Status.COMPLETED
            else "Receipt confirmed. Waiting for your partner."
        )
        serializer = TransactionDetailSerializer(
            exchange,
            context={"request": request},
        )
        return Response({"message": message, "transaction": serializer.data})
