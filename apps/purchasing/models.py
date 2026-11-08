import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimestampedModel


def generate_purchase_order_number():
    return f"PO-{uuid.uuid4().hex[:12].upper()}"


class PurchaseOrder(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ORDERED = "ORDERED", "Ordered"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially Received"
        RECEIVED = "RECEIVED", "Received"
        CANCELLED = "CANCELLED", "Cancelled"

    number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_purchase_order_number,
        editable=False,
    )

    supplier = models.ForeignKey(
        "partners.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    ordered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_purchase_orders",
    )

    def __str__(self):
        return self.number


class PurchaseOrderLine(TimestampedModel):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
    )

    quantity_ordered = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    quantity_received = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
    )

    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "product"],
                name="uniq_purchase_order_product",
            ),
            models.CheckConstraint(
                condition=Q(quantity_ordered__gt=0),
                name="po_line_quantity_ordered_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(quantity_received__gte=0),
                name="po_line_quantity_received_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(quantity_received__lte=F("quantity_ordered")),
                name="po_line_received_lte_ordered",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0),
                name="po_line_unit_cost_gte_zero",
            ),
        ]

    @property
    def quantity_remaining(self):
        return self.quantity_ordered - self.quantity_received

    def __str__(self):
        return f"{self.product} - {self.quantity_received}/{self.quantity_ordered}"


class Receipt(TimestampedModel):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name="receipts",
    )

    idempotency_key = models.UUIDField()

    request_hash = models.CharField(max_length=64)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_receipts",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order", "idempotency_key"],
                name="uniq_receipt_order_idempotency",
            ),
        ]

    def __str__(self):
        return f"Receipt #{self.pk} - {self.purchase_order.number}"


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(
        Receipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name="receipt_lines",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["receipt", "purchase_order_line"],
                name="uniq_receipt_purchase_order_line",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="receipt_line_quantity_gt_zero",
            ),
        ]

    def __str__(self):
        return f"{self.purchase_order_line.product} - {self.quantity}"
