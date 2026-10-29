from django.http import JsonResponse
from django.utils.cache import add_never_cache_headers


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
