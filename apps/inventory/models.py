from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimestampedModel


class Warehouse(TimestampedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"[{self.code}] {self.name}"


class StockLevel(TimestampedModel):
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="stock_levels",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="stock_levels",
    )
    on_hand = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    reserved = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "warehouse"],
                name="uniq_stock_level_product_warehouse",
            ),
            models.CheckConstraint(
                condition=Q(on_hand__gte=0),
                name="stock_on_hand_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(reserved__gte=0),
                name="stock_reserved_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(reserved__lte=F("on_hand")),
                name="stock_reserved_lte_on_hand",
            ),
        ]

    @property
    def available(self):
        return self.on_hand - self.reserved

    def __str__(self):
        return f"{self.product} @ {self.warehouse} : {self.on_hand} (Dispo: {self.available})"


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied("StockMovement is immutable and cannot be updated.")

    def delete(self):
        raise PermissionDenied("StockMovement is immutable and cannot be deleted.")


class ImmutableManager(models.Manager):
    def get_queryset(self):
        return ImmutableQuerySet(self.model, using=self._db)


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        RECEIPT = "RECEIPT", "Réception"
        SHIPMENT = "SHIPMENT", "Expédition"
        RESERVE = "RESERVE", "Réservation"
        RELEASE = "RELEASE", "Libération"
        ADJUSTMENT = "ADJUSTMENT", "Ajustement"

    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="stock_movements")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_movements")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    on_hand_delta = models.DecimalField(max_digits=12, decimal_places=3)
    reserved_delta = models.DecimalField(max_digits=12, decimal_places=3)
    reference = models.CharField(max_length=100, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_movements")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(~Q(movement_type="ADJUSTMENT") | ~Q(reason="")),
                name="adjustment_requires_reason",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionDenied("StockMovement is immutable and cannot be modified.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("StockMovement is immutable and cannot be deleted.")

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} | {self.movement_type} | {self.product.sku} ({self.warehouse.code})"
