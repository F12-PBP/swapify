from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView

from .forms import LoginForm, RegisterForm
from .models import Profile


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
