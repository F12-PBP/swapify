from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.core import signing
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.cache import patch_vary_headers
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.clothing_catalog.categories import DISCOVERY_TYPES, STYLE_CHOICES
from apps.clothing_catalog.forms import DiscoveryFilterForm
from apps.clothing_catalog.selectors import member_listings, viewer_coordinates
from apps.review_rating.models import Review
from apps.swap_request.models import SwapRequest
from common.redirects import safe_return_url

from .forms import (
    LocationCoordinatesForm,
    LoginForm,
    OnboardingLocationForm,
    OnboardingProfileForm,
    PreferencesForm,
    ProfileLocationForm,
    ProfilePhotoForm,
    ProfileUpdateForm,
    RegisterForm,
)
from .geocoding import GeocodingError, reverse_geocode
from .models import Profile
from .services import ProfilePhotoUploadError, upload_profile_picture


class LoginUserView(LoginView):
    template_name = "user_profile/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class RegisterUserView(CreateView):
    template_name = "user_profile/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("user_profile:onboarding")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("user_profile:detail")

        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        profile = self.object.profile
        profile.display_name = form.cleaned_data["name"]
        profile.save(update_fields=["display_name"])
        login(self.request, self.object)
        return response


class LogoutUserView(LogoutView):
    next_page = reverse_lazy("main:home")


class WardrobeView(TemplateView):
    template_name = "user_profile/profile_public.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("user_profile:public", username=request.user.username)
        return self.render_to_response({"guest_wardrobe": True})


def profile_style_choices():
    labels = dict(STYLE_CHOICES)
    return [
        (key, labels[key])
        for key in (
            "tops",
            "outerwear",
            "bottoms",
            "dresses",
            "bags",
            "accessories",
            "shoes",
        )
    ]


class ProfileDialogMixin:
    dialog_template_name = None

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "dialog_mode": self.request.headers.get("X-Profile-Dialog") == "1",
        }

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ["X-Profile-Dialog"])
        return response

    def get_template_names(self):
        if self.request.headers.get("X-Profile-Dialog") == "1":
            return [self.dialog_template_name]
        return super().get_template_names()

    def form_valid(self, form):
        response = super().form_valid(form)
        if (
            self.request.headers.get("X-Profile-Dialog") == "1"
            and response.status_code == 302
        ):
            return JsonResponse({"redirect": response.url})
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get("X-Profile-Dialog") == "1":
            response.status_code = 422
        return response


class MyProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "user_profile/profile_detail.html"
    context_object_name = "profile"

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reviews = Review.objects.filter(recipient=self.request.user).select_related(
            "author__profile"
        )
        context["rating_summary"] = reviews.aggregate(
            average=Avg("rating"), count=Count("pk")
        )
        context["latest_review"] = reviews.first()
        context["style_choices"] = profile_style_choices()
        return context


class MyReviewListView(LoginRequiredMixin, ListView):
    template_name = "user_profile/profile_reviews.html"
    context_object_name = "reviews"
    paginate_by = 10

    def get_queryset(self):
        self.received_reviews = Review.objects.filter(
            recipient=self.request.user
        ).select_related("author__profile")
        self.rating = self.request.GET.get("rating", "")
        if self.rating not in {"1", "2", "3", "4", "5"}:
            self.rating = ""
        return (
            self.received_reviews.filter(rating=self.rating)
            if self.rating
            else self.received_reviews
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rating"] = self.rating
        context["rating_choices"] = range(1, 6)
        context["rating_summary"] = self.received_reviews.aggregate(
            average=Avg("rating"), count=Count("pk")
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("X-Profile-Reviews") == "1":
            response = JsonResponse(
                {
                    "html": render_to_string(
                        "user_profile/partials/review_results.html",
                        context,
                        request=self.request,
                    )
                }
            )
        else:
            response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ["X-Profile-Reviews"])
        return response


class MyProfilePreferencesUpdateView(
    LoginRequiredMixin, ProfileDialogMixin, SuccessMessageMixin, UpdateView
):
    model = Profile
    form_class = PreferencesForm
    template_name = "user_profile/preferences_form.html"
    dialog_template_name = "user_profile/partials/preferences_form.html"
    success_url = reverse_lazy("user_profile:detail")
    success_message = "Your style preferences have been updated."

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "style_choices": profile_style_choices(),
        }


class MyProfileUpdateView(
    LoginRequiredMixin, ProfileDialogMixin, SuccessMessageMixin, UpdateView
):
    model = Profile
    form_class = ProfileUpdateForm
    template_name = "user_profile/profile_form.html"
    dialog_template_name = "user_profile/partials/profile_form.html"
    context_object_name = "profile"
    success_url = reverse_lazy("user_profile:detail")
    success_message = "Your profile has been updated."

    def get_object(self, queryset=None):
        return self.request.user.profile

    def form_valid(self, form):
        image = form.cleaned_data.get("new_profile_picture")

        if image is not None:
            try:
                picture = upload_profile_picture(
                    image=image,
                    user_id=self.request.user.pk,
                )
            except ProfilePhotoUploadError as error:
                form.add_error(
                    "new_profile_picture",
                    str(error),
                )
                return self.form_invalid(form)

            form.instance.profile_picture = picture

        return super().form_valid(form)


class MyProfileLocationUpdateView(
    LoginRequiredMixin, ProfileDialogMixin, SuccessMessageMixin, UpdateView
):
    model = Profile
    form_class = ProfileLocationForm
    template_name = "user_profile/location_form.html"
    dialog_template_name = "user_profile/partials/location_form.html"
    context_object_name = "profile"
    success_url = reverse_lazy("user_profile:detail")
    success_message = "Your location has been updated."

    def get_success_url(self):
        return safe_return_url(self.request, self.success_url)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "return_url": self.get_success_url(),
        }

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user_id": self.request.user.pk}


class LocationResolveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = LocationCoordinatesForm(request.POST)
        if not form.is_valid():
            return JsonResponse(
                {"error": "Please provide valid latitude and longitude."}, status=400
            )
        try:
            location = reverse_geocode(**form.cleaned_data)
        except GeocodingError as error:
            response = JsonResponse({"error": str(error)}, status=error.status_code)
            if error.status_code == 429:
                response["Retry-After"] = "2"
        else:
            token = signing.dumps(
                {**location, "user_id": request.user.pk}, salt="user_profile.location"
            )
            response = JsonResponse(
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


class PublicProfileDetailView(DetailView):
    model = Profile
    template_name = "user_profile/profile_public.html"
    context_object_name = "profile"

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("X-Member-Wardrobe") == "1":
            response = JsonResponse(
                {
                    "html": render_to_string(
                        "user_profile/partials/public_wardrobe_results.html",
                        context,
                        request=self.request,
                    ),
                    "filters": context["filters"],
                    "count": context["clothing_page"].paginator.count,
                }
            )
        else:
            response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ["X-Member-Wardrobe", "Cookie"])
        return response

    def get_queryset(self):
        return Profile.objects.select_related("user").filter(user__is_active=True)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset,
            user__username=self.kwargs["username"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        is_owner = (
            self.request.user.is_authenticated
            and self.request.user.pk == self.object.user_id
        )
        has_location = viewer_coordinates(self.request.user) is not None
        filter_form = DiscoveryFilterForm(self.request.GET, has_location=has_location)
        filter_form.is_valid()
        clothing_items = member_listings(
            self.request.user, self.object.user_id, filter_form.cleaned_data
        )
        if is_owner:
            pending_requests = SwapRequest.objects.filter(
                requested_clothing_id=OuterRef("pk"),
                status=SwapRequest.Status.PENDING,
            ).order_by("-created_at", "-pk")
            clothing_items = clothing_items.annotate(
                pending_request_id=Subquery(pending_requests.values("pk")[:1]),
            )
        context["is_owner"] = is_owner
        context["clothing_items"] = clothing_items
        context["clothing_page"] = Paginator(clothing_items, 12).get_page(
            self.request.GET.get("wardrobe_page")
        )
        context["wardrobe_filtered"] = any(
            filter_form.cleaned_data.get(key)
            for key in ("search", "type", "size", "condition", "distance")
        )
        context["filter_form"] = filter_form
        context["filters"] = filter_form.cleaned_data
        context["has_location"] = has_location
        context["categories"] = DISCOVERY_TYPES
        context["style_choices"] = profile_style_choices()
        default_tab = "wardrobe" if is_owner else "profile"
        if self.request.GET.get("reviews_page"):
            default_tab = "profile"
        requested_tab = self.request.GET.get("tab", default_tab)
        context["active_tab"] = (
            requested_tab if requested_tab in {"profile", "wardrobe"} else default_tab
        )

        received_reviews = Review.objects.filter(
            recipient_id=self.object.user_id,
        ).select_related("author__profile")

        context["rating_summary"] = received_reviews.aggregate(
            average=Avg("rating"),
            count=Count("pk"),
        )

        paginator = Paginator(received_reviews, 10)
        context["reviews_page"] = paginator.get_page(
            self.request.GET.get("reviews_page")
        )

        return context


class OnboardingView(LoginRequiredMixin, View):
    """Save each step independently, so members can safely finish later."""

    def get(self, request):
        try:
            step = min(4, max(1, int(request.GET.get("step", 1))))
        except (TypeError, ValueError):
            step = 1
        if step == 4 and not request.user.profile.onboarding_completed:
            step = 1
        return render(request, "user_profile/onboarding.html", self.context(step))

    def context(self, step, bound_form=None):
        profile = self.request.user.profile
        forms = [
            OnboardingProfileForm(instance=profile),
            OnboardingLocationForm(instance=profile, user_id=profile.user_id),
            PreferencesForm(instance=profile),
        ]
        if bound_form is not None:
            forms[step - 1] = bound_form
        return {
            "step": step,
            "profile_form": forms[0],
            "location_form": forms[1],
            "preferences_form": forms[2],
            "profile": profile,
            "step_labels": (
                "A little about you",
                "Your neighbourhood",
                "Your kind of style",
            ),
            "style_choices": forms[2].fields["preferences"].choices,
        }

    def post(self, request):
        if request.POST.get("action") == "upload_photo":
            form = ProfilePhotoForm(request.POST, request.FILES)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
            try:
                picture = upload_profile_picture(
                    image=form.cleaned_data["new_profile_picture"],
                    user_id=request.user.pk,
                )
            except ProfilePhotoUploadError as error:
                return JsonResponse({"error": str(error)}, status=400)
            profile = request.user.profile
            profile.profile_picture = picture
            profile.save(update_fields=["profile_picture"])
            return JsonResponse({"profile_picture_url": profile.profile_picture.url})
        if request.POST.get("action") == "later":
            return redirect("clothing_catalog:list")
        try:
            step = int(request.POST.get("step", 1))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid onboarding step."}, status=400)
        if step not in (1, 2, 3):
            return JsonResponse({"error": "Invalid onboarding step."}, status=400)
        profile = request.user.profile
        form_class = (OnboardingProfileForm, OnboardingLocationForm, PreferencesForm)[
            step - 1
        ]
        kwargs = {"instance": profile}
        if step == 2:
            kwargs["user_id"] = request.user.pk
        form = form_class(request.POST, request.FILES, **kwargs)
        if form.is_valid():
            if step == 1 and (image := form.cleaned_data.get("new_profile_picture")):
                try:
                    form.instance.profile_picture = upload_profile_picture(
                        image=image,
                        user_id=request.user.pk,
                    )
                except ProfilePhotoUploadError as error:
                    form.add_error("new_profile_picture", str(error))
            if not form.errors:
                with transaction.atomic():
                    form.save()
                    if step == 3:
                        profile.onboarding_completed = True
                        profile.save(update_fields=["onboarding_completed"])
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {"step": step + 1, "display_name": profile.display_name}
                    )
                return redirect(f"{reverse('user_profile:onboarding')}?step={step + 1}")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        return render(request, "user_profile/onboarding.html", self.context(step, form))
