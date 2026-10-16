from django.db import models
from apps.core.models import TimestampedModel
from django.db.models.functions import Lower
from django.db.models import Q

# Create your models here.


class Category(TimestampedModel):
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="uniq_category_name_ci",
            )
        ]

    def __str__(self):
        return self.name


class Product(TimestampedModel):
    sku = models.CharField(max_length=40)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="products")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("sku"),
                name="uniq_product_sku_ci",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="product_price_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(reorder_level__gte=0),
                name="product_reorder_level_gte_0",
            ),
        ]

    def __str__(self):
        return f"[{self.sku}] {self.name}"
