from rest_framework import serializers

from apps.partners.models import Customer, Supplier


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_email(self, value):
        if value is None:
            return value
        return value.strip().lower()

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("The name cannot be empty.")
        return value.strip()


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_email(self, value):
        if value is None:
            return value
        return value.strip().lower()

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("The name cannot be empty.")
        return value.strip()
