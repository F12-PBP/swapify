from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import DiscoveryFilterForm
from .models import Clothing
from .selectors import (
    discover_listings,
    filter_listings,
    listings_with_owners,
    viewer_coordinates,
)
from .serializers import ClothingSerializer, ClothingWriteSerializer


class ClothingPagination(PageNumberPagination):
    page_size = 12


def paginated_response(request, queryset):
    paginator = ClothingPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(ClothingSerializer(page, many=True).data)


class ClothingListCreateAPIView(APIView):
    authentication_classes = [SessionAuthentication]

    def get_permissions(self):
        return [IsAuthenticated() if self.request.method == "POST" else AllowAny()]

    def get(self, request):
        form = DiscoveryFilterForm(
            request.query_params,
            has_location=bool(viewer_coordinates(request.user)),
        )
        filters = form.cleaned_data if form.is_valid() else {}
        return paginated_response(request, discover_listings(request.user, filters))

    def post(self, request):
        serializer = ClothingWriteSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        clothing = serializer.save(owner=request.user)
        return Response(
            ClothingSerializer(clothing).data,
            status=status.HTTP_201_CREATED,
        )


class MyClothingListAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        form = DiscoveryFilterForm(request.query_params)
        filters = form.cleaned_data if form.is_valid() else {}
        queryset = listings_with_owners().filter(owner=request.user)
        queryset = filter_listings(queryset, request.user, filters)
        if request.query_params.get("status") in Clothing.Status.values:
            queryset = queryset.filter(status=request.query_params["status"])
        return paginated_response(request, queryset)


class ClothingDetailAPIView(APIView):
    authentication_classes = [SessionAuthentication]

    def get_permissions(self):
        return [AllowAny() if self.request.method == "GET" else IsAuthenticated()]

    def get_object(self, uuid):
        return get_object_or_404(Clothing.objects.select_related("owner"), uuid=uuid)

    def get(self, request, uuid):
        return Response(ClothingSerializer(self.get_object(uuid)).data)

    def _owned_available_object(self, request, uuid):
        clothing = self.get_object(uuid)
        if (
            clothing.owner_id != request.user.pk
            or clothing.status != Clothing.Status.AVAILABLE
        ):
            raise PermissionDenied("You cannot change this clothing item.")
        return clothing

    def patch(self, request, uuid):
        clothing = self._owned_available_object(request, uuid)
        serializer = ClothingWriteSerializer(
            clothing,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        clothing = serializer.save()
        return Response(ClothingSerializer(clothing).data)

    def delete(self, request, uuid):
        self._owned_available_object(request, uuid).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
