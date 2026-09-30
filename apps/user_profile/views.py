# Create your views here.

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from .models import Profile


class MyProfileDetailView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = "user_profile/profile_detail.html"
    context_object_name = "profile"

    def get_object(self):
        return self.request.user.profile
