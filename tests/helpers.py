from django.db.models import Sum

from apps.inventory.models import StockLevel, StockMovement


def assert_ledger_consistent():
    """
    Verify that StockLevel matches the sum
    of all StockMovement entries.
    """

    for level in StockLevel.objects.all():
        totals = StockMovement.objects.filter(
            product=level.product,
            warehouse=level.warehouse,
        ).aggregate(
            on_hand_total=Sum("on_hand_delta"),
            reserved_total=Sum("reserved_delta"),
        )

        expected_on_hand = totals["on_hand_total"] or 0
        expected_reserved = totals["reserved_total"] or 0

        assert expected_on_hand == level.on_hand, f"Stock mismatch for product {level.product_id}: expected {expected_on_hand}, got {level.on_hand}"

        assert expected_reserved == level.reserved, f"Reserved mismatch for product {level.product_id}: expected {expected_reserved}, got {level.reserved}"
