from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimestampedModel


class SalesOrder(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        CONFIRMED = "CONFIRMED", "Confirmed"
        SHIPPED = "SHIPPED", "Shipped"
        CANCELLED = "CANCELLED", "Cancelled"

    number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )

    customer = models.ForeignKey(
        "partners.Customer",
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_sales_orders",
    )

    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    shipped_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="sales_status_created_idx",
            ),
            models.Index(
                fields=["customer", "created_at"],
                name="sales_customer_created_idx",
            ),
        ]

    def __str__(self):
        return self.number or f"Sales order #{self.pk}"

    @property
    def total(self):
        lines = self.lines.all()

        if any(line.unit_price is None for line in lines):
            return None

        return sum(
            (line.line_total for line in lines),
            start=Decimal("0.00"),
        )


class SalesOrderLine(models.Model):
    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="sales_order_lines",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="uniq_sales_order_product",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="sales_line_quantity_gt_0",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__isnull=True) | Q(unit_price__gte=0),
                name="sales_line_price_gte_0",
            ),
        ]

    def __str__(self):
        return f"{self.order} - {self.product}"

    @property
    def line_total(self):
        if self.unit_price is None:
            return None

        return self.quantity * self.unit_price
