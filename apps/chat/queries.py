MAX_ID = (1 << 63) - 1


def after_cursor(request):
    try:
        value = int(request.GET.get("after", 0))
    except (TypeError, ValueError):
        return 0

    return value if 0 <= value <= MAX_ID else 0
