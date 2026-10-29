import logging

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import Http404, JsonResponse
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.views.csrf import csrf_failure as default_csrf_failure

logger = logging.getLogger(__name__)


def wants_json(request):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    accepts_json = "application/json" in request.headers.get("Accept", "")
    return is_ajax or accepts_json


def json_response(data, *, status=200):
    response = JsonResponse(data, status=status)
    add_never_cache_headers(response)
    return response


def error_response(code, message, *, status, **extra):
    return json_response(
        {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
            **extra,
        },
        status=status,
    )


def login_required_response(request):
    match = request.resolver_match
    pk = match.kwargs.get("pk") if match else None

    next_url = reverse("chat:detail", args=[pk]) if pk else reverse("chat:list")
    login_url = redirect_to_login(
        next_url,
        resolve_url(settings.LOGIN_URL),
    )["Location"]

    return error_response(
        "login_required",
        "Sesi login berakhir. Silakan masuk kembali.",
        status=401,
        login_url=login_url,
    )


class JsonChatMixin:
    def handle_no_permission(self):
        if wants_json(self.request):
            return login_required_response(self.request)

        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)

        except Http404:
            if not wants_json(request):
                raise

            return error_response(
                "not_found",
                "Chat tidak ditemukan atau tidak dapat diakses.",
                status=404,
            )

        except PermissionDenied:
            if not wants_json(request):
                raise

            return error_response(
                "forbidden",
                "Kamu tidak diizinkan mengakses chat ini.",
                status=403,
            )

        except DatabaseError:
            if not wants_json(request):
                raise

            logger.exception("Database chat tidak tersedia")

            return error_response(
                "temporarily_unavailable",
                "Layanan chat sedang bermasalah. Coba kembali nanti.",
                status=503,
            )


def csrf_failure(request, reason=""):
    match = request.resolver_match

    if match and match.namespace == "chat" and wants_json(request):
        if not request.user.is_authenticated:
            return login_required_response(request)

        return error_response(
            "csrf_failed",
            "Token keamanan tidak valid. Muat ulang halaman sebelum mencoba lagi.",
            status=403,
        )

    return default_csrf_failure(request, reason=reason)
