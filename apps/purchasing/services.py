import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.audit import record_audit
from apps.core.exceptions import (
    EmptyOrder,
    IdempotencyConflict,
    InvalidTransition,
    OverReceipt,
)
from apps.inventory.models import StockMovement
from apps.inventory.services import apply_stock_change

from .models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    ReceiptLine,
)


def place_purchase_order(*, purchase_order_id, user):
    """
    Transition DRAFT -> ORDERED.
    """

    with transaction.atomic():
        order = PurchaseOrder.objects.select_for_update().get(pk=purchase_order_id)

        if order.status != PurchaseOrder.Status.DRAFT:
            raise InvalidTransition("Only draft purchase orders can be placed.")

        if not order.supplier.is_active:
            raise InvalidTransition("Cannot place an order for an inactive supplier.")

        if not order.warehouse.is_active:
            raise InvalidTransition("Cannot place an order for an inactive warehouse.")

        if not order.lines.exists():
            raise EmptyOrder("A purchase order must contain at least one line.")

        order.status = PurchaseOrder.Status.ORDERED
        order.ordered_at = timezone.now()

        order.save(update_fields=["status", "ordered_at", "updated_at"])

        record_audit(
            user=user,
            action="purchase_order.placed",
            obj=order,
            payload={
                "number": order.number,
            },
        )

        return order


def cancel_purchase_order(*, purchase_order_id, user):
    """
    Cancel a DRAFT or ORDERED purchase order
    if nothing has been received.
    """

    with transaction.atomic():
        order = PurchaseOrder.objects.select_for_update().get(pk=purchase_order_id)

        if order.status not in (
            PurchaseOrder.Status.DRAFT,
            PurchaseOrder.Status.ORDERED,
        ):
            raise InvalidTransition("This purchase order cannot be cancelled.")

        if order.lines.filter(quantity_received__gt=0).exists():
            raise InvalidTransition("A purchase order with received quantities cannot be cancelled.")

        order.status = PurchaseOrder.Status.CANCELLED

        order.save(update_fields=["status", "updated_at"])

        record_audit(
            user=user,
            action="purchase_order.cancelled",
            obj=order,
            payload={
                "number": order.number,
            },
        )

        return order


def _normalize_receipt_lines(lines):
    """
    Aggregate duplicate purchase_order_line entries.

    Example:
        line 1: 5
        line 1: 3

    Result:
        line 1: 8
    """

    aggregated = defaultdict(lambda: Decimal("0"))

    for item in lines:
        line_id = int(item["purchase_order_line_id"])
        quantity = Decimal(str(item["quantity"]))

        if quantity <= 0:
            raise OverReceipt("Receipt quantity must be greater than zero.")

        aggregated[line_id] += quantity

    return dict(aggregated)


def _receipt_hash(aggregated_lines):
    """
    Generate a stable SHA256 hash of the request.
    """

    canonical_data = [
        {
            "purchase_order_line_id": line_id,
            "quantity": str(quantity),
        }
        for line_id, quantity in sorted(aggregated_lines.items())
    ]

    payload = json.dumps(
        canonical_data,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def receive_purchase_order(
    *,
    purchase_order_id,
    idempotency_key,
    lines,
    user,
):
    """
    Receive goods for a purchase order.

    Returns:
        (receipt, replayed)

    replayed is True when the request was already processed.
    """

    aggregated_lines = _normalize_receipt_lines(lines)

    if not aggregated_lines:
        raise EmptyOrder("At least one receipt line is required.")

    request_hash = _receipt_hash(aggregated_lines)

    with transaction.atomic():
        # 1. Lock the purchase order.
        order = PurchaseOrder.objects.select_for_update().get(pk=purchase_order_id)

        # 2. Check idempotency before checking order status.
        # This allows a successful request to be replayed
        # even if the order has since become RECEIVED.
        existing_receipt = Receipt.objects.filter(
            purchase_order=order,
            idempotency_key=idempotency_key,
        ).first()

        if existing_receipt:
            if existing_receipt.request_hash != request_hash:
                raise IdempotencyConflict("This idempotency key was already used with another payload.")

            return existing_receipt, True

        # 3. Validate order status.
        if order.status not in (
            PurchaseOrder.Status.ORDERED,
            PurchaseOrder.Status.PARTIALLY_RECEIVED,
        ):
            raise InvalidTransition("Goods can only be received for ordered purchase orders.")

        # 4. Lock all order lines in deterministic order.
        order_lines = list(PurchaseOrderLine.objects.select_for_update().filter(purchase_order=order).order_by("product_id", "pk"))

        lines_by_id = {line.pk: line for line in order_lines}

        # 5. Validate ALL requested lines before writing anything.
        validated_lines = []

        for line_id, quantity in sorted(aggregated_lines.items()):
            po_line = lines_by_id.get(line_id)

            if po_line is None:
                raise InvalidTransition(
                    "A receipt line does not belong to this purchase order.",
                    {
                        "purchase_order_line": line_id,
                    },
                )

            remaining = po_line.quantity_ordered - po_line.quantity_received

            if quantity > remaining:
                raise OverReceipt(
                    "Received quantity exceeds the remaining quantity.",
                    {
                        "purchase_order_line": po_line.pk,
                        "remaining": str(remaining),
                        "requested": str(quantity),
                    },
                )

            validated_lines.append((po_line, quantity))

        # 6. Create the receipt.
        try:
            with transaction.atomic():
                receipt = Receipt.objects.create(
                    purchase_order=order,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    received_by=user,
                )

        except IntegrityError:
            # A concurrent request may have created the same key.
            existing_receipt = Receipt.objects.filter(
                purchase_order=order,
                idempotency_key=idempotency_key,
            ).first()

            if existing_receipt is None:
                raise

            if existing_receipt.request_hash != request_hash:
                raise IdempotencyConflict("This idempotency key was already used with another payload.")

            return existing_receipt, True

        # 7. Apply stock changes and create receipt lines.
        for po_line, quantity in validated_lines:
            ReceiptLine.objects.create(
                receipt=receipt,
                purchase_order_line=po_line,
                quantity=quantity,
            )

            apply_stock_change(
                product_id=po_line.product_id,
                warehouse_id=order.warehouse_id,
                movement_type=StockMovement.MovementType.RECEIPT,
                on_hand_delta=quantity,
                user=user,
                reference=order.number,
            )

            po_line.quantity_received += quantity

            po_line.save(
                update_fields=[
                    "quantity_received",
                    "updated_at",
                ]
            )

        # 8. Recalculate the order status.
        order_lines = list(PurchaseOrderLine.objects.filter(purchase_order=order))

        all_received = all(line.quantity_received == line.quantity_ordered for line in order_lines)

        if all_received:
            order.status = PurchaseOrder.Status.RECEIVED
        else:
            order.status = PurchaseOrder.Status.PARTIALLY_RECEIVED

        order.save(update_fields=["status", "updated_at"])

        # 9. Audit event.
        record_audit(
            user=user,
            action="purchase_order.received",
            obj=order,
            payload={
                "number": order.number,
                "receipt_id": receipt.pk,
                "lines": [
                    {
                        "purchase_order_line": line.pk,
                        "quantity": str(quantity),
                    }
                    for line, quantity in validated_lines
                ],
                "status": order.status,
            },
        )

        return receipt, False
