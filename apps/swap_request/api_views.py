from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clothing_catalog.models import Clothing

from .forms import SwapRequestFilterForm
from .models import SwapRequest
from .serializers import SwapRequestCreateSerializer, SwapRequestSerializer
from .services import (
    SwapAcceptanceError,
    SwapCreationError,
    accept_swap_request,
    create_swap_request,
)


class SwapRequestPagination(PageNumberPagination):
    page_size = 8


def swap_requests_for(user):
    return SwapRequest.objects.for_user(user).with_card_details(user)


def serialized_swap_request(request, pk):
    swap_request = swap_requests_for(request.user).get(pk=pk)
    return SwapRequestSerializer(swap_request, context={"request": request}).data


class SwapRequestListCreateAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        filters = SwapRequestFilterForm(request.query_params).values
        queryset = (
            swap_requests_for(user)
            .search(filters["search"])
            .order_by("-created_at", "-pk")
        )
        if filters["role"] == "sent":
            queryset = queryset.filter(requester=user)
        elif filters["role"] == "received":
            queryset = queryset.filter(requested_clothing__owner=user)
        if filters["status"]:
            queryset = queryset.filter(status=filters["status"])

        paginator = SwapRequestPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = SwapRequestSerializer(
            page,
            many=True,
            context={"request": request},
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        input_serializer = SwapRequestCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        clothing_ids = dict(
            Clothing.objects.filter(
                uuid__in=[data["requested_clothing"], data["offered_clothing"]]
            ).values_list("uuid", "pk")
        )
        missing = {
            field: "Clothing not found."
            for field in ("requested_clothing", "offered_clothing")
            if data[field] not in clothing_ids
        }
        if missing:
            raise DRFValidationError(missing)

        try:
            swap_request = create_swap_request(
                requester=request.user,
                requested_clothing_id=clothing_ids[data["requested_clothing"]],
                offered_clothing_id=clothing_ids[data["offered_clothing"]],
                message=data["message"],
            )
        except SwapCreationError as error:
            raise DRFValidationError({"detail": str(error)}) from error

        return Response(
            serialized_swap_request(request, swap_request.pk),
            status=status.HTTP_201_CREATED,
        )


class SwapRequestDetailAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        swap_request = get_object_or_404(swap_requests_for(request.user), pk=pk)
        serializer = SwapRequestSerializer(
            swap_request,
            context={"request": request},
        )
        return Response(serializer.data)


class SwapRequestActionAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    new_status = None
    success_message = ""

    def get_queryset(self):
        raise NotImplementedError

    def post(self, request, pk):
        swap_request = get_object_or_404(self.get_queryset(), pk=pk)
        with transaction.atomic():
            changed = self.update_status(swap_request)
            if not changed:
                transaction.set_rollback(True)

        if not changed:
            return Response(
                {"detail": self.failure_message(swap_request)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "detail": self.success_message,
                "swap_request": serialized_swap_request(request, swap_request.pk),
            }
        )

    def update_status(self, swap_request):
        updated = SwapRequest.objects.filter(
            pk=swap_request.pk, status=SwapRequest.Status.PENDING
        ).update(status=self.new_status, updated_at=timezone.now())
        return updated == 1

    def failure_message(self, swap_request):
        swap_request.refresh_from_db()
        if swap_request.status != SwapRequest.Status.PENDING:
            current = swap_request.get_status_display().lower()
            return f"This swap request was already {current}, so it can't be changed."
        return "This swap request can't be changed right now. Please try again."


class OwnerActionAPIView(SwapRequestActionAPIView):
    def get_queryset(self):
        return SwapRequest.objects.filter(requested_clothing__owner=self.request.user)


class SwapRequestAcceptAPIView(OwnerActionAPIView):
    new_status = SwapRequest.Status.ACCEPTED
    success_message = "Swap accepted. Say hello in Messages to plan the handover."

    def update_status(self, swap_request):
        try:
            accept_swap_request(
                request_id=swap_request.pk,
                acting_user=self.request.user,
            )
        except (SwapAcceptanceError, DjangoValidationError):
            return False
        return True

    def failure_message(self, swap_request):
        message = super().failure_message(swap_request)
        blocking = swap_request.blocking_clothing
        if blocking:
            return (
                f"{blocking.name} is already part of another swap, "
                "so this request can't be accepted."
            )
        return message


class SwapRequestRejectAPIView(OwnerActionAPIView):
    new_status = SwapRequest.Status.REJECTED
    success_message = "Swap request rejected."


class SwapRequestCancelAPIView(SwapRequestActionAPIView):
    new_status = SwapRequest.Status.CANCELLED
    success_message = "Swap request cancelled."

    def get_queryset(self):
        return SwapRequest.objects.filter(requester=self.request.user)
