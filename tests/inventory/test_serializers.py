from decimal import Decimal

import pytest

from apps.inventory.serializers import (
    StockAdjustmentInputSerializer,
)


@pytest.mark.django_db
def test_adjustment_serializer_valid_data(
    product,
    warehouse,
):

    serializer = StockAdjustmentInputSerializer(
        data={
            "product": product.id,
            "warehouse": warehouse.id,
            "quantity_delta": "5.000",
            "reason": "Physical correction",
        }
    )

    assert serializer.is_valid(), serializer.errors

    assert serializer.validated_data["quantity_delta"] == 5
    assert serializer.validated_data["quantity_delta"] == Decimal("5.000")


@pytest.mark.django_db
def test_adjustment_serializer_rejects_zero(
    product,
    warehouse,
):

    serializer = StockAdjustmentInputSerializer(
        data={
            "product": product.id,
            "warehouse": warehouse.id,
            "quantity_delta": "0.000",
            "reason": "Test",
        }
    )

    assert not serializer.is_valid()

    assert "quantity_delta" in serializer.errors


@pytest.mark.django_db
def test_adjustment_serializer_rejects_blank_reason(
    product,
    warehouse,
):

    serializer = StockAdjustmentInputSerializer(
        data={
            "product": product.id,
            "warehouse": warehouse.id,
            "quantity_delta": "5.000",
            "reason": "   ",
        }
    )

    assert not serializer.is_valid()

    assert "reason" in serializer.errors
