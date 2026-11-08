from decimal import Decimal
from uuid import uuid4

import pytest

from apps.core.exceptions import (
    IdempotencyConflict,
    InvalidTransition,
    OverReceipt,
)
from apps.inventory.models import StockLevel, StockMovement
from apps.purchasing.models import (
    PurchaseOrder,
    Receipt,
)
from apps.purchasing.services import (
    cancel_purchase_order,
    place_purchase_order,
    receive_purchase_order,
)

pytestmark = pytest.mark.django_db


def receive(order, line, quantity, user, key=None):
    return receive_purchase_order(
        purchase_order_id=order.pk,
        idempotency_key=key or uuid4(),
        lines=[
            {
                "purchase_order_line_id": line.pk,
                "quantity": Decimal(quantity),
            }
        ],
        user=user,
    )


def get_stock(order, product):
    return StockLevel.objects.get(
        product=product,
        warehouse=order.warehouse,
    )


def test_place_purchase_order(purchase_order, purchaser):

    purchase_order.status = PurchaseOrder.Status.DRAFT
    purchase_order.save(update_fields=["status"])

    result = place_purchase_order(
        purchase_order_id=purchase_order.pk,
        user=purchaser,
    )

    assert result.status == PurchaseOrder.Status.ORDERED
    assert result.ordered_at is not None


def test_cancel_draft_order(purchase_order, purchaser):

    purchase_order.status = PurchaseOrder.Status.DRAFT
    purchase_order.save(update_fields=["status"])

    result = cancel_purchase_order(
        purchase_order_id=purchase_order.pk,
        user=purchaser,
    )

    assert result.status == PurchaseOrder.Status.CANCELLED


def test_partial_receipt(
    purchase_order,
    purchase_order_line,
    stock_manager,
    product,
):

    receipt, replayed = receive(
        purchase_order,
        purchase_order_line,
        "10.000",
        stock_manager,
    )

    purchase_order.refresh_from_db()
    purchase_order_line.refresh_from_db()

    stock = get_stock(purchase_order, product)

    assert replayed is False
    assert receipt.pk is not None

    assert purchase_order.status == (PurchaseOrder.Status.PARTIALLY_RECEIVED)

    assert purchase_order_line.quantity_received == Decimal("10.000")
    assert stock.on_hand == Decimal("10.000")

    movement = StockMovement.objects.get(
        reference=purchase_order.number,
        movement_type=StockMovement.MovementType.RECEIPT,
    )

    assert movement.on_hand_delta == Decimal("10.000")


def test_complete_receipt(
    purchase_order,
    purchase_order_line,
    stock_manager,
):

    receive(
        purchase_order,
        purchase_order_line,
        "10.000",
        stock_manager,
    )

    receive(
        purchase_order,
        purchase_order_line,
        "15.000",
        stock_manager,
    )

    purchase_order.refresh_from_db()
    purchase_order_line.refresh_from_db()

    assert purchase_order.status == PurchaseOrder.Status.RECEIVED

    assert purchase_order_line.quantity_received == Decimal("25.000")


def test_over_receipt_is_rejected(
    purchase_order,
    purchase_order_line,
    stock_manager,
    product,
):

    with pytest.raises(OverReceipt):
        receive(
            purchase_order,
            purchase_order_line,
            "30.000",
            stock_manager,
        )

    purchase_order.refresh_from_db()
    purchase_order_line.refresh_from_db()

    assert purchase_order_line.quantity_received == Decimal("0.000")

    assert purchase_order.status == PurchaseOrder.Status.ORDERED

    assert not StockLevel.objects.filter(
        product=product,
        warehouse=purchase_order.warehouse,
    ).exists()

    assert (
        Receipt.objects.filter(
            purchase_order=purchase_order,
        ).count()
        == 0
    )


def test_idempotent_replay(
    purchase_order,
    purchase_order_line,
    stock_manager,
    product,
):

    key = uuid4()

    first_receipt, first_replayed = receive(
        purchase_order,
        purchase_order_line,
        "10.000",
        stock_manager,
        key,
    )

    second_receipt, second_replayed = receive(
        purchase_order,
        purchase_order_line,
        "10.000",
        stock_manager,
        key,
    )

    stock = get_stock(purchase_order, product)

    assert first_replayed is False
    assert second_replayed is True

    assert first_receipt.pk == second_receipt.pk

    assert (
        Receipt.objects.filter(
            purchase_order=purchase_order,
        ).count()
        == 1
    )

    assert stock.on_hand == Decimal("10.000")

    assert (
        StockMovement.objects.filter(
            reference=purchase_order.number,
            movement_type=StockMovement.MovementType.RECEIPT,
        ).count()
        == 1
    )


def test_same_key_different_payload_is_rejected(
    purchase_order,
    purchase_order_line,
    stock_manager,
):

    key = uuid4()

    receive(
        purchase_order,
        purchase_order_line,
        "10.000",
        stock_manager,
        key,
    )

    with pytest.raises(IdempotencyConflict):
        receive(
            purchase_order,
            purchase_order_line,
            "5.000",
            stock_manager,
            key,
        )


def test_duplicate_lines_are_aggregated(
    purchase_order,
    purchase_order_line,
    stock_manager,
    product,
):

    receive_purchase_order(
        purchase_order_id=purchase_order.pk,
        idempotency_key=uuid4(),
        lines=[
            {
                "purchase_order_line_id": purchase_order_line.pk,
                "quantity": Decimal("10.000"),
            },
            {
                "purchase_order_line_id": purchase_order_line.pk,
                "quantity": Decimal("15.000"),
            },
        ],
        user=stock_manager,
    )

    purchase_order_line.refresh_from_db()

    stock = get_stock(purchase_order, product)

    assert purchase_order_line.quantity_received == Decimal("25.000")
    assert stock.on_hand == Decimal("25.000")


def test_duplicate_lines_over_remaining_are_rejected(
    purchase_order,
    purchase_order_line,
    stock_manager,
    product,
):

    with pytest.raises(OverReceipt):
        receive_purchase_order(
            purchase_order_id=purchase_order.pk,
            idempotency_key=uuid4(),
            lines=[
                {
                    "purchase_order_line_id": purchase_order_line.pk,
                    "quantity": Decimal("15.000"),
                },
                {
                    "purchase_order_line_id": purchase_order_line.pk,
                    "quantity": Decimal("15.000"),
                },
            ],
            user=stock_manager,
        )

    purchase_order_line.refresh_from_db()

    assert purchase_order_line.quantity_received == Decimal("0.000")

    assert not StockLevel.objects.filter(
        product=product,
        warehouse=purchase_order.warehouse,
    ).exists()


def test_cannot_receive_cancelled_order(
    purchase_order,
    purchase_order_line,
    stock_manager,
):

    purchase_order.status = PurchaseOrder.Status.CANCELLED
    purchase_order.save(update_fields=["status"])

    with pytest.raises(InvalidTransition):
        receive(
            purchase_order,
            purchase_order_line,
            "5.000",
            stock_manager,
        )


def test_cannot_cancel_after_partial_receipt(
    purchase_order,
    purchase_order_line,
    stock_manager,
    purchaser,
):

    receive(
        purchase_order,
        purchase_order_line,
        "10.000",
        stock_manager,
    )

    with pytest.raises(InvalidTransition):
        cancel_purchase_order(
            purchase_order_id=purchase_order.pk,
            user=purchaser,
        )


def test_receipt_creates_stock_level(
    purchase_order,
    purchase_order_line,
    stock_manager,
    product,
):

    assert not StockLevel.objects.filter(
        product=product,
        warehouse=purchase_order.warehouse,
    ).exists()

    receive(
        purchase_order,
        purchase_order_line,
        "5.000",
        stock_manager,
    )

    stock = get_stock(purchase_order, product)

    assert stock.on_hand == Decimal("5.000")
