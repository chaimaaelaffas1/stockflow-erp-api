from django.db import transaction
from rest_framework import serializers

from .models import SalesOrder, SalesOrderLine


class SalesOrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    line_total = serializers.DecimalField(
        max_digits=24,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = SalesOrderLine
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "line_total",
        ]

        read_only_fields = [
            "id",
            "unit_price",
            "line_total",
        ]


class SalesOrderSerializer(serializers.ModelSerializer):
    lines = SalesOrderLineSerializer(many=True)

    customer_name = serializers.CharField(
        source="customer.name",
        read_only=True,
    )

    warehouse_name = serializers.CharField(
        source="warehouse.name",
        read_only=True,
    )

    total = serializers.DecimalField(
        max_digits=24,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = SalesOrder
        fields = [
            "id",
            "number",
            "customer",
            "customer_name",
            "warehouse",
            "warehouse_name",
            "status",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
            "confirmed_at",
            "shipped_at",
            "cancelled_at",
            "lines",
            "total",
        ]

        read_only_fields = [
            "id",
            "number",
            "status",
            "created_by",
            "created_at",
            "updated_at",
            "confirmed_at",
            "shipped_at",
            "cancelled_at",
            "total",
        ]

    def validate(self, attrs):
        instance = self.instance

        if instance and instance.status != SalesOrder.Status.DRAFT:
            raise serializers.ValidationError("Only DRAFT orders can be modified.")

        customer = attrs.get(
            "customer",
            instance.customer if instance else None,
        )

        warehouse = attrs.get(
            "warehouse",
            instance.warehouse if instance else None,
        )

        if customer and not customer.is_active:
            raise serializers.ValidationError({"customer": "The customer is inactive."})

        if warehouse and not warehouse.is_active:
            raise serializers.ValidationError({"warehouse": "The warehouse is inactive."})

        lines = attrs.get("lines")

        if lines is not None:
            product_ids = [line["product"].pk for line in lines]

            if len(product_ids) != len(set(product_ids)):
                raise serializers.ValidationError({"lines": "A product can appear only once in an order."})

            for line in lines:
                if not line["product"].is_active:
                    raise serializers.ValidationError({"lines": "Inactive products cannot be ordered."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        request = self.context["request"]

        order = SalesOrder.objects.create(
            created_by=request.user,
            **validated_data,
        )

        order.number = f"SO-{order.pk:06d}"
        order.save(update_fields=["number"])

        SalesOrderLine.objects.bulk_create(
            [
                SalesOrderLine(
                    order=order,
                    product=line["product"],
                    quantity=line["quantity"],
                )
                for line in lines_data
            ]
        )

        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()

            SalesOrderLine.objects.bulk_create(
                [
                    SalesOrderLine(
                        order=instance,
                        product=line["product"],
                        quantity=line["quantity"],
                    )
                    for line in lines_data
                ]
            )

        return instance
