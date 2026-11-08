from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.catalog.models import Product
from apps.inventory.models import Warehouse
from apps.partners.models import Supplier

from .models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    ReceiptLine,
)


class PurchaseOrderLineWriteSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "product",
            "quantity_ordered",
            "unit_cost",
        ]

    def validate_quantity_ordered(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Quantity ordered must be greater than zero.")
        return value

    def validate_unit_cost(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError("Unit cost cannot be negative.")
        return value


class PurchaseOrderLineReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )

    quantity_remaining = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity_ordered",
            "quantity_received",
            "quantity_remaining",
            "unit_cost",
        ]


class PurchaseOrderReadSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source="supplier.name",
        read_only=True,
    )

    warehouse_name = serializers.CharField(
        source="warehouse.name",
        read_only=True,
    )

    lines = PurchaseOrderLineReadSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "number",
            "supplier",
            "supplier_name",
            "warehouse",
            "warehouse_name",
            "status",
            "ordered_at",
            "created_by",
            "created_at",
            "updated_at",
            "lines",
        ]
        read_only_fields = fields


class PurchaseOrderWriteSerializer(serializers.ModelSerializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())

    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())

    lines = PurchaseOrderLineWriteSerializer(
        many=True,
        required=False,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "supplier",
            "warehouse",
            "lines",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):

        supplier = attrs.get(
            "supplier",
            getattr(self.instance, "supplier", None),
        )

        warehouse = attrs.get(
            "warehouse",
            getattr(self.instance, "warehouse", None),
        )

        if supplier and not supplier.is_active:
            raise serializers.ValidationError({"supplier": "Supplier must be active."})

        if warehouse and not warehouse.is_active:
            raise serializers.ValidationError({"warehouse": "Warehouse must be active."})

        if "lines" in attrs:
            products = [item["product"].pk for item in attrs["lines"]]

            if len(products) != len(set(products)):
                raise serializers.ValidationError({"lines": "A product can only appear once in a purchase order."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):

        lines_data = validated_data.pop("lines", [])

        order = PurchaseOrder.objects.create(**validated_data)

        for line_data in lines_data:
            PurchaseOrderLine.objects.create(
                purchase_order=order,
                **line_data,
            )

        return order

    @transaction.atomic
    def update(self, instance, validated_data):

        lines_data = validated_data.pop("lines", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if lines_data is not None:
            if instance.status != PurchaseOrder.Status.DRAFT:
                raise serializers.ValidationError("Only draft purchase orders can be edited.")

            if instance.lines.filter(quantity_received__gt=0).exists():
                raise serializers.ValidationError("Cannot replace lines after receiving goods.")

            instance.lines.all().delete()

            for line_data in lines_data:
                PurchaseOrderLine.objects.create(
                    purchase_order=instance,
                    **line_data,
                )

        return instance


class ReceiveLineInputSerializer(serializers.Serializer):
    purchase_order_line = serializers.IntegerField(
        min_value=1,
    )

    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )


class ReceiveInputSerializer(serializers.Serializer):
    idempotency_key = serializers.UUIDField()

    lines = ReceiveLineInputSerializer(
        many=True,
        allow_empty=False,
    )


class ReceiptLineReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="purchase_order_line.product.name",
        read_only=True,
    )

    product_sku = serializers.CharField(
        source="purchase_order_line.product.sku",
        read_only=True,
    )

    class Meta:
        model = ReceiptLine
        fields = [
            "id",
            "purchase_order_line",
            "product_name",
            "product_sku",
            "quantity",
        ]


class ReceiptReadSerializer(serializers.ModelSerializer):
    purchase_order_number = serializers.CharField(
        source="purchase_order.number",
        read_only=True,
    )

    lines = ReceiptLineReadSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Receipt
        fields = [
            "id",
            "purchase_order",
            "purchase_order_number",
            "idempotency_key",
            "received_by",
            "created_at",
            "lines",
        ]
        read_only_fields = fields
