from django import template

register = template.Library()


@register.simple_tag
def marketplace_section(request):
    match = request.resolver_match
    if match is None:
        return ""
    if match.namespace == "clothing_catalog":
        return "discover" if match.url_name in {"list", "detail"} else "wardrobe"
    return {
        "swap_request": "swaps",
        "chat": "messages",
        "user_profile": "wardrobe",
    }.get(match.namespace, "")
