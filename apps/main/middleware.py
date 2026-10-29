"""
TEMPORARY AUTO-LOGIN MIDDLEWARE FOR TESTING ONLY
Remove this before production deployment.
"""

from django.contrib.auth import get_user_model, login


class AutoLoginMiddleware:
    """Auto-login testuser1 for development testing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            User = get_user_model()
            try:
                user = User.objects.get(username="testuser1")
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )
            except User.DoesNotExist:
                pass

        return self.get_response(request)
