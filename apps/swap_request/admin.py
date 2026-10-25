from django.contrib import admin

from .models import SwapRequest


@admin.register(SwapRequest)
class SwapRequestAdmin(admin.ModelAdmin):
    list_display = (
        "requester",
        "offered_clothing",
        "requested_clothing",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "requester__username",
        "offered_clothing__name",
        "requested_clothing__name",
    )
    list_select_related = ("requester", "offered_clothing", "requested_clothing")
