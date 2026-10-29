MAX_ID = (1 << 63) - 1
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


class InvalidMessageQuery(ValueError):
    pass


def after_cursor(request):
    try:
        value = int(request.GET.get("after", 0))
    except (TypeError, ValueError):
        return 0

    return value if 0 <= value <= MAX_ID else 0


def positive_integer(value, name, *, maximum=MAX_ID):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise InvalidMessageQuery(f"{name} harus berupa bilangan bulat.") from None

    if not 1 <= number <= maximum:
        raise InvalidMessageQuery(f"{name} harus berada di antara 1 dan {maximum}.")

    return number


def page_parameters(request):
    limit = positive_integer(
        request.GET.get("limit", DEFAULT_PAGE_SIZE),
        "limit",
        maximum=MAX_PAGE_SIZE,
    )

    if "before" in request.GET:
        if "after" in request.GET:
            raise InvalidMessageQuery("Gunakan salah satu: after atau before.")

        return (
            "older",
            positive_integer(request.GET["before"], "before"),
            limit,
        )

    return "newer", after_cursor(request), limit


def message_page(room, *, direction, cursor=0, limit=DEFAULT_PAGE_SIZE):
    queryset = room.messages.select_related("sender")

    if direction == "newer":
        queryset = queryset.filter(id__gt=cursor).order_by("id")
    else:
        if direction == "older":
            queryset = queryset.filter(id__lt=cursor)

        queryset = queryset.order_by("-id")

    rows = list(queryset[: limit + 1])
    has_more = len(rows) > limit
    batch = rows[:limit]

    if direction != "newer":
        batch.reverse()

    return batch, has_more
