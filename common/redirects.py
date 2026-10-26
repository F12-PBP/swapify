from django.utils.http import url_has_allowed_host_and_scheme


def safe_return_url(request, default):
    """Honor a local return destination after a form, never an external redirect."""
    target = request.POST.get("next") or request.GET.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return str(default)
