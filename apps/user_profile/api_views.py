from django.contrib.auth import authenticate, login, logout
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import (
    LocationCoordinatesForm,
    OnboardingLocationForm,
    OnboardingProfileForm,
    PreferencesForm,
    ProfileLocationForm,
    ProfilePhotoForm,
    RegisterForm,
)
from .geocoding import GeocodingError, reverse_geocode
from .models import Profile
from .serializers import ProfileSerializer
from .services import ProfilePhotoUploadError, upload_profile_picture


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "CSRF cookie is set."})


@method_decorator(csrf_protect, name="dispatch")
class LoginAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not isinstance(username, str) or not isinstance(password, str):
            return Response(
                {"detail": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)

        return Response(
            {
                "detail": "Login successful.",
                "user": {
                    "id": user.pk,
                    "username": user.get_username(),
                },
            }
        )


class LogoutAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)

        return Response(
            {"detail": "Logout successful."},
            status=status.HTTP_200_OK,
        )


class MyProfileAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(
            request.user.profile,
            context={"request": request},
        )
        return Response(serializer.data)

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user.profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


class PublicProfileAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, username):
        profile = get_object_or_404(
            Profile.objects.select_related("user"),
            user__username=username,
            user__is_active=True,
        )

        serializer = ProfileSerializer(
            profile,
            context={"request": request},
        )

        return Response(serializer.data)


@method_decorator(csrf_protect, name="dispatch")
class RegisterAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        form = RegisterForm(request.data)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user = form.save()
            user.profile.display_name = form.cleaned_data["name"]
            user.profile.save(update_fields=["display_name"])
            login(request, user)
        return Response(
            ProfileSerializer(user.profile).data, status=status.HTTP_201_CREATED
        )


class ProfilePhotoAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        form = ProfilePhotoForm(request.data, request.FILES)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            picture = upload_profile_picture(
                form.cleaned_data["new_profile_picture"], request.user.pk
            )
        except ProfilePhotoUploadError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        profile = request.user.profile
        profile.profile_picture = picture
        profile.save(update_fields=["profile_picture"])
        return Response(ProfileSerializer(profile).data)


class LocationResolveAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        form = LocationCoordinatesForm(request.data)
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            location = reverse_geocode(**form.cleaned_data)
        except GeocodingError as error:
            response = Response({"detail": str(error)}, status=error.status_code)
            if error.status_code == 429:
                response["Retry-After"] = "2"
        else:
            token = signing.dumps(
                {**location, "user_id": request.user.pk}, salt="user_profile.location"
            )
            response = Response(
                {
                    **{
                        field: location[field]
                        for field in ProfileLocationForm.Meta.fields
                    },
                    "location_token": token,
                }
            )
        response["Cache-Control"] = "no-store"
        return response


class ProfileLocationAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request):
        form = ProfileLocationForm(
            request.data, instance=request.user.profile, user_id=request.user.pk
        )
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        form.save()
        return Response(ProfileSerializer(request.user.profile).data)


class OnboardingAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, step):
        profile = request.user.profile
        if step == 1:
            form = OnboardingProfileForm(request.data, request.FILES, instance=profile)
        elif step == 2:
            form = OnboardingLocationForm(
                request.data, instance=profile, user_id=request.user.pk
            )
        elif step == 3:
            form = PreferencesForm(request.data, instance=profile)
        else:
            return Response(
                {"detail": "Invalid onboarding step."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not form.is_valid():
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        image = form.cleaned_data.get("new_profile_picture")
        if image:
            try:
                form.instance.profile_picture = upload_profile_picture(
                    image, request.user.pk
                )
            except ProfilePhotoUploadError as error:
                return Response(
                    {"new_profile_picture": [str(error)]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        with transaction.atomic():
            form.save()
            if step == 3:
                profile.onboarding_completed = True
                profile.save(update_fields=["onboarding_completed"])
        return Response({"step": step + 1, "profile": ProfileSerializer(profile).data})
