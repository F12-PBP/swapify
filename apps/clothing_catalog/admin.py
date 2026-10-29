from django.contrib import admin

from .models import Clothing


@admin.register(Clothing)
class ClothingAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "type", "size", "condition", "status")
    list_filter = ("type", "condition", "status")
    search_fields = ("name", "description", "owner__username")
    list_select_related = ("owner",)
