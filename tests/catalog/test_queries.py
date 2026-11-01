import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Product

User = get_user_model()

BASE_URL = "/api/v1/catalog/products/"


@pytest.mark.django_db
def test_product_list_uses_join_for_category(
    category,
    user_factory,
    api_client_for,
):
    for index in range(3):
        Product.objects.create(
            sku=f"QUERY-{index}",
            name=f"Product {index}",
            category=category,
            unit_price="100.00",
        )

    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    with CaptureQueriesContext(connection) as queries:
        response = client.get(BASE_URL)

    assert response.status_code == 200

    product_selects = [query["sql"].lower() for query in queries.captured_queries if "select" in query["sql"].lower() and "catalog_product" in query["sql"].lower()]

    assert any("join" in query for query in product_selects)
