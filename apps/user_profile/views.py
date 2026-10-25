from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from apps.clothing_catalog.models import Clothing

from .forms import LoginForm, ProfileUpdateForm, RegisterForm
from .models import Profile
from .services import ProfilePhotoUploadError, upload_profile_picture


class LoginUserView(LoginView):
    template_name = "user_profile/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class RegisterUserView(CreateView):
    template_name = "user_profile/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("user_profile:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("user_profile:detail")

        return super().dispatch(request, *args, **kwargs)

    @transaction.atomic
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Account created. You can now log in.")
        return response


class LogoutUserView(LogoutView):
    next_page = reverse_lazy("main:home")


class MyProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "user_profile/profile_detail.html"
    context_object_name = "profile"

    def get_object(self, queryset=None):
        return self.request.user.profile


class MyProfileUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Profile
    form_class = ProfileUpdateForm
    template_name = "user_profile/profile_form.html"
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


class PublicProfileDetailView(DetailView):
    model = Profile
    template_name = "user_profile/profile_public.html"
    context_object_name = "profile"

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

        context["clothing_items"] = Clothing.objects.filter(
            owner_id=self.object.user_id,
            status=Clothing.Status.AVAILABLE,
        ).order_by("-created_at")

        return context
