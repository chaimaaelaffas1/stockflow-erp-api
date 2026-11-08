from django.contrib import admin

from .models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    ReceiptLine,
)


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "supplier",
        "warehouse",
        "status",
        "ordered_at",
    ]

    list_filter = [
        "status",
        "ordered_at",
    ]

    search_fields = [
        "number",
        "supplier__name",
    ]

    inlines = [
        PurchaseOrderLineInline,
    ]

    readonly_fields = [
        "number",
        "created_by",
    ]


class ReceiptLineInline(admin.TabularInline):
    model = ReceiptLine
    extra = 0
    readonly_fields = [
        "purchase_order_line",
        "quantity",
    ]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "purchase_order",
        "received_by",
        "created_at",
    ]

    readonly_fields = [
        "purchase_order",
        "idempotency_key",
        "request_hash",
        "received_by",
        "created_at",
    ]

    inlines = [
        ReceiptLineInline,
    ]
