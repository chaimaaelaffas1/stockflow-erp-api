import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Product

User = get_user_model()

BASE_URL = "/api/v1/catalog/products/"


@pytest.mark.django_db
def test_filter_products_by_category(
    category,
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(
        BASE_URL,
        {"category": category.id},
    )

    assert response.status_code == 200
    assert all(item["category"] == category.id for item in response.data["results"])


@pytest.mark.django_db
def test_filter_products_by_active_status(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(
        BASE_URL,
        {"is_active": "true"},
    )

    assert response.status_code == 200
    assert all(item["is_active"] is True for item in response.data["results"])


@pytest.mark.django_db
def test_search_products_by_name(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(
        BASE_URL,
        {"search": "Produit test"},
    )

    assert response.status_code == 200
    assert any(item["id"] == product.id for item in response.data["results"])


@pytest.mark.django_db
def test_search_products_by_sku(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(
        BASE_URL,
        {"search": product.sku},
    )

    assert response.status_code == 200
    assert any(item["id"] == product.id for item in response.data["results"])


@pytest.mark.django_db
def test_order_products_by_unit_price(
    category,
    user_factory,
    api_client_for,
):
    Product.objects.create(
        sku="PRICE-001",
        name="Cheap product",
        category=category,
        unit_price="10.00",
    )
    Product.objects.create(
        sku="PRICE-002",
        name="Expensive product",
        category=category,
        unit_price="100.00",
    )

    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(
        BASE_URL,
        {"ordering": "unit_price"},
    )

    assert response.status_code == 200

    prices = [float(item["unit_price"]) for item in response.data["results"]]

    assert prices == sorted(prices)


@pytest.mark.django_db
def test_order_products_by_name(
    category,
    user_factory,
    api_client_for,
):
    Product.objects.create(
        sku="NAME-001",
        name="Zebra",
        category=category,
        unit_price="20.00",
    )
    Product.objects.create(
        sku="NAME-002",
        name="Apple",
        category=category,
        unit_price="30.00",
    )

    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(
        BASE_URL,
        {"ordering": "name"},
    )

    assert response.status_code == 200

    names = [item["name"] for item in response.data["results"]]

    assert names == sorted(names)
