from decimal import Decimal

import pytest
from django.db import transaction
from django.db.models import Sum

from apps.core.exceptions import (
    BusinessRuleError,
    InsufficientStock,
)
from apps.inventory.models import (
    StockLevel,
    StockMovement,
)
from apps.inventory.services import (
    adjust_stock,
    apply_stock_change,
)
from tests.helpers import assert_ledger_consistent


@pytest.mark.django_db
def test_adjust_stock_positive(product, warehouse, user):

    movement = adjust_stock(
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity_delta=Decimal("10"),
        reason="Initial stock correction",
        user=user,
    )

    level = StockLevel.objects.get(
        product=product,
        warehouse=warehouse,
    )

    assert level.on_hand == Decimal("10")
    assert level.reserved == Decimal("0")
    assert level.available == Decimal("10")

    assert movement.movement_type == "ADJUSTMENT"

    assert movement.on_hand_delta == Decimal("10")
    assert movement.reserved_delta == Decimal("0")

    assert StockMovement.objects.count() == 1


@pytest.mark.django_db
def test_adjust_stock_negative(product, warehouse, user):

    adjust_stock(
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity_delta=Decimal("10"),
        reason="Initial stock",
        user=user,
    )

    movement = adjust_stock(
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity_delta=Decimal("-4"),
        reason="Physical inventory correction",
        user=user,
    )

    level = StockLevel.objects.get(
        product=product,
        warehouse=warehouse,
    )

    assert level.on_hand == Decimal("6")
    assert level.reserved == Decimal("0")
    assert level.available == Decimal("6")

    assert movement.on_hand_delta == Decimal("-4")

    assert StockMovement.objects.count() == 2


@pytest.mark.django_db
def test_adjust_stock_insufficient(
    product,
    warehouse,
    user,
):

    adjust_stock(
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity_delta=Decimal("10"),
        reason="Initial stock",
        user=user,
    )

    with pytest.raises(InsufficientStock):
        adjust_stock(
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity_delta=Decimal("-15"),
            reason="Incorrect adjustment",
            user=user,
        )

    level = StockLevel.objects.get(
        product=product,
        warehouse=warehouse,
    )

    assert level.on_hand == Decimal("10")

    assert StockMovement.objects.count() == 1


@pytest.mark.django_db
def test_adjustment_cannot_go_below_reserved(
    product,
    warehouse,
    user,
):

    with transaction.atomic():
        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="RECEIPT",
            on_hand_delta=Decimal("10"),
            user=user,
        )

        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="RESERVE",
            reserved_delta=Decimal("6"),
            user=user,
        )

    with pytest.raises(InsufficientStock):
        adjust_stock(
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity_delta=Decimal("-5"),
            reason="Incorrect correction",
            user=user,
        )

    level = StockLevel.objects.get(
        product=product,
        warehouse=warehouse,
    )

    assert level.on_hand == Decimal("10")
    assert level.reserved == Decimal("6")
    assert level.available == Decimal("4")


@pytest.mark.django_db
def test_adjustment_requires_reason(
    product,
    warehouse,
    user,
):

    with pytest.raises(BusinessRuleError):
        adjust_stock(
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity_delta=Decimal("5"),
            reason="   ",
            user=user,
        )

    assert StockMovement.objects.count() == 0


@pytest.mark.django_db
def test_adjustment_zero_not_allowed(
    product,
    warehouse,
    user,
):

    with pytest.raises(BusinessRuleError):
        adjust_stock(
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity_delta=Decimal("0"),
            reason="Zero adjustment",
            user=user,
        )

    assert StockMovement.objects.count() == 0


@pytest.mark.django_db
def test_stock_accounting_invariant(
    product,
    warehouse,
    user,
):

    with transaction.atomic():
        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="RECEIPT",
            on_hand_delta=Decimal("10"),
            user=user,
        )

        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="RESERVE",
            reserved_delta=Decimal("3"),
            user=user,
        )

        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="RELEASE",
            reserved_delta=Decimal("-1"),
            user=user,
        )

        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="ADJUSTMENT",
            on_hand_delta=Decimal("2"),
            user=user,
            reason="Inventory correction",
        )

        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="SHIPMENT",
            on_hand_delta=Decimal("-2"),
            reserved_delta=Decimal("-2"),
            user=user,
        )

    level = StockLevel.objects.get(
        product=product,
        warehouse=warehouse,
    )

    totals = StockMovement.objects.filter(
        product=product,
        warehouse=warehouse,
    ).aggregate(
        total_on_hand=Sum("on_hand_delta"),
        total_reserved=Sum("reserved_delta"),
    )

    assert totals["total_on_hand"] == level.on_hand
    assert totals["total_reserved"] == level.reserved


@pytest.mark.django_db(transaction=True)
def test_apply_stock_change_requires_transaction(
    product,
    warehouse,
    user,
):

    with pytest.raises(RuntimeError):
        apply_stock_change(
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type="ADJUSTMENT",
            on_hand_delta=Decimal("5"),
            user=user,
        )


@pytest.mark.django_db
def test_ledger_consistency_after_stock_operations(
    product,
    warehouse,
    user,
):
    with transaction.atomic():
        apply_stock_change(
            product_id=product.pk,
            warehouse_id=warehouse.pk,
            movement_type="RECEIPT",
            on_hand_delta=Decimal("20"),
            user=user,
        )

        apply_stock_change(
            product_id=product.pk,
            warehouse_id=warehouse.pk,
            movement_type="RESERVE",
            reserved_delta=Decimal("5"),
            user=user,
        )

        apply_stock_change(
            product_id=product.pk,
            warehouse_id=warehouse.pk,
            movement_type="RELEASE",
            reserved_delta=Decimal("-2"),
            user=user,
        )

        apply_stock_change(
            product_id=product.pk,
            warehouse_id=warehouse.pk,
            movement_type="ADJUSTMENT",
            on_hand_delta=Decimal("3"),
            user=user,
            reason="Inventory correction",
        )

    assert_ledger_consistent()
