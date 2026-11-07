from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.core.exceptions import BusinessRuleError, InsufficientStock

from .models import StockLevel, StockMovement


def _locked_level(product_id, warehouse_id):

    # Step 1: Create the stock level if it does not exist.
    # The nested atomic block creates a savepoint.
    try:
        with transaction.atomic():
            StockLevel.objects.get_or_create(
                product_id=product_id,
                warehouse_id=warehouse_id,
            )

    except IntegrityError:
        # Another transaction may have created it.
        pass

    # Step 2: Lock the existing stock level.
    level = StockLevel.objects.select_for_update().get(
        product_id=product_id,
        warehouse_id=warehouse_id,
    )

    return level


def apply_stock_change(
    *,
    product_id,
    warehouse_id,
    movement_type,
    on_hand_delta=Decimal("0"),
    reserved_delta=Decimal("0"),
    user,
    reference="",
    reason="",
):
    # STEP 1: Verify that we are inside a transaction.
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("apply_stock_change must run inside transaction.atomic()")

    # STEP 2: Lock the stock level.
    level = _locked_level(product_id, warehouse_id)

    # STEP 3: Calculate the new values.
    new_on_hand = level.on_hand + on_hand_delta
    new_reserved = level.reserved + reserved_delta

    # STEP 4: Validate business rules.
    if new_on_hand < 0 or new_reserved < 0 or new_reserved > new_on_hand:
        raise InsufficientStock(
            "Not enough available stock.",
            {
                "product": product_id,
                "warehouse": warehouse_id,
                "available": str(level.available),
                "requested_change": str(on_hand_delta or reserved_delta),
            },
        )

    # STEP 5: Update StockLevel.
    level.on_hand = new_on_hand
    level.reserved = new_reserved

    level.save(
        update_fields=[
            "on_hand",
            "reserved",
            "updated_at",
        ]
    )

    # STEP 6: Create StockMovement.
    movement = StockMovement.objects.create(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        on_hand_delta=on_hand_delta,
        reserved_delta=reserved_delta,
        reference=reference,
        reason=reason,
        created_by=user,
    )

    # STEP 7: Return the created movement.
    return movement


@transaction.atomic
def adjust_stock(
    *,
    product_id,
    warehouse_id,
    quantity_delta,
    reason,
    user,
):

    # STEP 1: Verify the reason.
    if not reason or not reason.strip():
        raise BusinessRuleError("A reason is required for stock adjustments.")

    # STEP 2: Reject a zero adjustment.
    if quantity_delta == 0:
        raise BusinessRuleError("Adjustment cannot be zero.")

    # STEP 3: Apply the stock change.
    return apply_stock_change(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=StockMovement.MovementType.ADJUSTMENT,
        on_hand_delta=quantity_delta,
        user=user,
        reason=reason.strip(),
    )
