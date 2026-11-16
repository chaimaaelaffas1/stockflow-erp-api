from decimal import Decimal

import pytest

from apps.catalog.models import Category, Product
from apps.inventory.models import StockLevel, Warehouse


@pytest.mark.django_db
def test_dashboard_summary_returns_correct_values(
    api_client_for,
    user_factory,
):
    user = user_factory(role="ADMIN")

    category = Category.objects.create(name="Dashboard category")

    product = Product.objects.create(
        sku="DASH-001",
        name="Dashboard product",
        category=category,
        unit_price=Decimal("10.00"),
    )

    warehouse = Warehouse.objects.create(
        code="DASH-01",
        name="Dashboard warehouse",
    )

    StockLevel.objects.create(
        product=product,
        warehouse=warehouse,
        on_hand=Decimal("5.000"),
        reserved=Decimal("2.000"),
    )

    client = api_client_for(user)

    response = client.get("/api/v1/dashboard/summary/")

    assert response.status_code == 200

    assert response.data["products_count"] == 1

    assert response.data["active_products_count"] == 1

    assert response.data["products_out_of_stock"] == 0

    assert response.data["stock_value_at_list_price"] == "50"

    assert response.data["sales_orders_by_status"] == {}

    assert response.data["purchase_orders_by_status"] == {}
