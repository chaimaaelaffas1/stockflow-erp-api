import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Product

User = get_user_model()

BASE_URL = "/api/v1/catalog/products/"


@pytest.mark.django_db
def test_admin_can_create_product(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    payload = {
        "sku": "drill-001",
        "name": "Perceuse",
        "description": "Perceuse électrique",
        "category": category.id,
        "unit_price": "250.00",
        "is_active": True,
        "reorder_level": "5.000",
    }

    response = client.post(
        BASE_URL,
        payload,
        format="json",
    )

    assert response.status_code == 201
    assert Product.objects.filter(sku="DRILL-001").exists()


@pytest.mark.django_db
def test_stock_manager_can_create_product(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.STOCK_MANAGER)
    client = api_client_for(user)

    payload = {
        "sku": "TOOL-001",
        "name": "Tool",
        "category": category.id,
        "unit_price": "100.00",
    }

    response = client.post(BASE_URL, payload, format="json")

    assert response.status_code == 201


@pytest.mark.django_db
def test_viewer_cannot_create_product(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {
            "sku": "TOOL-002",
            "name": "Tool",
            "category": category.id,
            "unit_price": "100.00",
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_product_sku_is_normalized(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {
            "sku": "  drill-002 ",
            "name": "Perceuse",
            "category": category.id,
            "unit_price": "100.00",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["sku"] == "DRILL-002"


@pytest.mark.django_db
def test_duplicate_product_sku_is_rejected(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {
            "sku": product.sku.lower(),
            "name": "Another product",
            "category": product.category_id,
            "unit_price": "150.00",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_negative_product_price_is_rejected(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {
            "sku": "TOOL-003",
            "name": "Tool",
            "category": category.id,
            "unit_price": "-10.00",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_product_can_be_updated(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.patch(
        f"{BASE_URL}{product.id}/",
        {"name": "New product name"},
        format="json",
    )

    assert response.status_code == 200
    product.refresh_from_db()
    assert product.name == "New product name"


@pytest.mark.django_db
def test_product_can_be_deactivated(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        f"{BASE_URL}{product.id}/deactivate/",
    )

    assert response.status_code == 200

    product.refresh_from_db()
    assert product.is_active is False


@pytest.mark.django_db
def test_deactivate_is_idempotent(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    url = f"{BASE_URL}{product.id}/deactivate/"

    first_response = client.post(url)
    second_response = client.post(url)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    product.refresh_from_db()
    assert product.is_active is False


@pytest.mark.django_db
def test_product_delete_is_not_allowed(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.delete(f"{BASE_URL}{product.id}/")

    assert response.status_code == 405
    assert Product.objects.filter(id=product.id).exists()
