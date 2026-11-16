import pytest
from rest_framework.test import APIClient

PROTECTED_GET_ENDPOINTS = [
    "/api/v1/auth/me/",
    "/api/v1/users/",
    "/api/v1/partners/customers/",
    "/api/v1/partners/suppliers/",
    "/api/v1/catalog/categories/",
    "/api/v1/catalog/products/",
    "/api/v1/inventory/warehouses/",
    "/api/v1/inventory/stock-levels/",
    "/api/v1/inventory/stock-movements/",
    "/api/v1/sales/sales-orders/",
    "/api/v1/purchasing/purchase-orders/",
    "/api/v1/purchasing/receipts/",
]


@pytest.mark.parametrize("url", PROTECTED_GET_ENDPOINTS)
@pytest.mark.django_db
def test_protected_endpoints_require_authentication(url):
    client = APIClient()

    response = client.get(url)

    assert response.status_code == 401, (
        f"{url} should require authentication. Received {response.status_code}"
    )
