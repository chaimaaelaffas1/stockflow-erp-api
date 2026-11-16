from rest_framework import serializers

from apps.core.models import AuditLog


class DashboardSummarySerializer(serializers.Serializer):
    products_count = serializers.IntegerField()
    active_products_count = serializers.IntegerField()
    categories_count = serializers.IntegerField()

    customers_count = serializers.IntegerField()
    suppliers_count = serializers.IntegerField()
    warehouses_count = serializers.IntegerField()

    products_out_of_stock = serializers.IntegerField()
    products_low_stock = serializers.IntegerField()

    stock_value_at_list_price = serializers.CharField()

    sales_orders_by_status = serializers.DictField(child=serializers.IntegerField())

    purchase_orders_by_status = serializers.DictField(child=serializers.IntegerField())


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(
        source="actor.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AuditLog

        fields = [
            "id",
            "actor",
            "actor_email",
            "action",
            "object_type",
            "object_id",
            "payload",
            "created_at",
        ]

        read_only_fields = fields
