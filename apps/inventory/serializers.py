from rest_framework import serializers

from .models import StockLevel, StockMovement, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "is_active",
        ]
        read_only_fields = ["id"]


class StockLevelSerializer(serializers.ModelSerializer):
    available = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )

    class Meta:
        model = StockLevel
        fields = [
            "id",
            "product",
            "warehouse",
            "on_hand",
            "reserved",
            "available",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "available",
            "updated_at",
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            "id",
            "product",
            "warehouse",
            "movement_type",
            "on_hand_delta",
            "reserved_delta",
            "reference",
            "reason",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class StockAdjustmentInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=StockLevel._meta.get_field("product").remote_field.model.objects.all())

    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())

    quantity_delta = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    reason = serializers.CharField(
        required=True,
        allow_blank=False,
    )

    def validate_quantity_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("Adjustment cannot be zero.")
        return value

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("A reason is required.")
        return value.strip()
