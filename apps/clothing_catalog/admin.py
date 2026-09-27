from django.contrib import admin

from .models import Clothing


@admin.register(Clothing)
class ClothingAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "size", "condition", "availability")
    list_filter = ("category", "condition", "availability")
    search_fields = ("name", "description", "owner__username")
    list_select_related = ("owner",)
