import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


# endpoint, rôles autorisés, données nécessaires
ENDPOINTS = [
    (
        "/api/v1/catalog/categories/",
        {"ADMIN", "STOCK_MANAGER"},
        {"name": "Category permission test"},
    ),
    (
        "/api/v1/catalog/products/",
        {"ADMIN", "STOCK_MANAGER"},
        None,
    ),
    (
        "/api/v1/partners/customers/",
        {"ADMIN", "SALES"},
        {"name": "Customer permission test"},
    ),
    (
        "/api/v1/partners/suppliers/",
        {"ADMIN", "PURCHASER"},
        {"name": "Supplier permission test"},
    ),
    (
        "/api/v1/inventory/warehouses/",
        {"ADMIN", "STOCK_MANAGER"},
        {"code": "PERM-01", "name": "Permission warehouse"},
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,allowed_roles,payload",
    ENDPOINTS,
)
def test_create_endpoint_permissions(
    url,
    allowed_roles,
    payload,
    user_factory,
    api_client_for,
):
    all_roles = {
        "ADMIN",
        "STOCK_MANAGER",
        "SALES",
        "PURCHASER",
        "VIEWER",
    }

    for role in all_roles:
        user = user_factory(
            email=f"{role.lower()}@example.com",
            role=role,
        )

        client = api_client_for(user)

        response = client.post(
            url,
            payload or {},
            format="json",
        )

        if role in allowed_roles:
            assert response.status_code not in (401, 403), (
                f"{role} should be allowed on {url}. "
                f"Received {response.status_code}: {response.data}"
            )
        else:
            assert response.status_code == 403, (
                f"{role} should be forbidden on {url}. "
                f"Received {response.status_code}: {response.data}"
            )
