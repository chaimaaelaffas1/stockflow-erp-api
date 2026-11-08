from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.partners.models import Supplier
from apps.purchasing.models import (
    PurchaseOrder,
    PurchaseOrderLine,
)


@pytest.fixture
def supplier(db):
    return Supplier.objects.create(
        name="Fournisseur test",
        email="supplier-test@example.com",
    )


@pytest.fixture
def purchaser(user_factory):
    return user_factory(
        email="purchaser@atlas.ma",
        role=User.Role.PURCHASER,
    )


@pytest.fixture
def stock_manager(user_factory):
    return user_factory(
        email="stock-manager@atlas.ma",
        role=User.Role.STOCK_MANAGER,
    )


@pytest.fixture
def purchase_order(
    db,
    supplier,
    warehouse,
    product,
    purchaser,
):
    order = PurchaseOrder.objects.create(
        supplier=supplier,
        warehouse=warehouse,
        status=PurchaseOrder.Status.ORDERED,
        created_by=purchaser,
    )

    PurchaseOrderLine.objects.create(
        purchase_order=order,
        product=product,
        quantity_ordered=Decimal("25.000"),
        quantity_received=Decimal("0.000"),
        unit_cost=Decimal("50.00"),
    )

    return order


@pytest.fixture
def purchase_order_line(purchase_order):
    return purchase_order.lines.get()
