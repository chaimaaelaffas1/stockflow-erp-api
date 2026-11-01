from django.contrib import admin

from apps.catalog.models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "created_at",
        "updated_at",
    ]

    search_fields = ["name"]

    ordering = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "sku",
        "name",
        "category",
        "unit_price",
        "is_active",
    ]

    list_filter = [
        "is_active",
        "category",
    ]

    search_fields = [
        "sku",
        "name",
    ]

    ordering = ["sku"]

    list_select_related = ["category"]
