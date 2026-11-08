from django.db import transaction
from django.utils import timezone

from apps.core.audit import record_audit
from apps.core.exceptions import (
    BusinessRuleError,
    InvalidTransition,
)
from apps.inventory.models import StockMovement
from apps.inventory.services import apply_stock_change

from .models import SalesOrder


def _get_locked_order(order_id):
    try:
        return SalesOrder.objects.select_for_update().select_related("customer", "warehouse").get(pk=order_id)
    except SalesOrder.DoesNotExist:
        raise SalesOrder.DoesNotExist


@transaction.atomic
def confirm_sales_order(order_id, user):
    order = _get_locked_order(order_id)

    if order.status != SalesOrder.Status.DRAFT:
        raise InvalidTransition(
            "Only DRAFT orders can be confirmed.",
            {"current_status": order.status},
        )

    if not order.customer.is_active:
        raise BusinessRuleError(
            "The customer is inactive.",
            {"customer": order.customer_id},
        )

    if not order.warehouse.is_active:
        raise BusinessRuleError(
            "The warehouse is inactive.",
            {"warehouse": order.warehouse_id},
        )

    lines = list(order.lines.select_related("product").order_by("product_id"))

    if not lines:
        raise BusinessRuleError(
            "A sales order must contain at least one line.",
            {"order": order.pk},
        )

    for line in lines:
        product = line.product

        if not product.is_active:
            raise BusinessRuleError(
                "A product in this order is inactive.",
                {"product": product.pk},
            )

        apply_stock_change(
            product_id=product.pk,
            warehouse_id=order.warehouse_id,
            movement_type=StockMovement.MovementType.RESERVE,
            reserved_delta=line.quantity,
            user=user,
            reference=order.number or f"SO-{order.pk:06d}",
        )

        line.unit_price = product.unit_price
        line.save(update_fields=["unit_price"])

    order.status = SalesOrder.Status.CONFIRMED
    order.confirmed_at = timezone.now()

    order.save(
        update_fields=[
            "status",
            "confirmed_at",
            "updated_at",
        ]
    )

    record_audit(
        user=user,
        action="sales_order.confirmed",
        obj=order,
        payload={
            "number": order.number,
            "lines_count": len(lines),
        },
    )

    return order


@transaction.atomic
def ship_sales_order(order_id, user):
    order = _get_locked_order(order_id)

    if order.status != SalesOrder.Status.CONFIRMED:
        raise InvalidTransition(
            "Only CONFIRMED orders can be shipped.",
            {"current_status": order.status},
        )

    lines = list(order.lines.select_related("product").order_by("product_id"))

    for line in lines:
        apply_stock_change(
            product_id=line.product_id,
            warehouse_id=order.warehouse_id,
            movement_type=StockMovement.MovementType.SHIPMENT,
            on_hand_delta=-line.quantity,
            reserved_delta=-line.quantity,
            user=user,
            reference=order.number,
        )

    order.status = SalesOrder.Status.SHIPPED
    order.shipped_at = timezone.now()

    order.save(
        update_fields=[
            "status",
            "shipped_at",
            "updated_at",
        ]
    )

    record_audit(
        user=user,
        action="sales_order.shipped",
        obj=order,
        payload={"number": order.number},
    )

    return order


@transaction.atomic
def cancel_sales_order(order_id, user):
    order = _get_locked_order(order_id)

    if order.status not in [
        SalesOrder.Status.DRAFT,
        SalesOrder.Status.CONFIRMED,
    ]:
        raise InvalidTransition(
            "Only DRAFT or CONFIRMED orders can be cancelled.",
            {"current_status": order.status},
        )

    if order.status == SalesOrder.Status.CONFIRMED:
        lines = list(order.lines.select_related("product").order_by("product_id"))

        for line in lines:
            apply_stock_change(
                product_id=line.product_id,
                warehouse_id=order.warehouse_id,
                movement_type=StockMovement.MovementType.RELEASE,
                reserved_delta=-line.quantity,
                user=user,
                reference=order.number,
                reason="Sales order cancelled",
            )

    order.status = SalesOrder.Status.CANCELLED
    order.cancelled_at = timezone.now()

    order.save(
        update_fields=[
            "status",
            "cancelled_at",
            "updated_at",
        ]
    )

    record_audit(
        user=user,
        action="sales_order.cancelled",
        obj=order,
        payload={"number": order.number},
    )

    return order
