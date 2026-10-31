import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.accounts.models import User
from apps.partners.models import Customer, Supplier


@pytest.mark.django_db
def test_customer_search(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Customer.objects.create(name="Atlas Distribution")
    Customer.objects.create(name="Other Company")

    response = client.get(
        reverse("customer-list"),
        {"search": "Atlas"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "Atlas Distribution"


@pytest.mark.django_db
def test_customer_filter_by_active_status(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Customer.objects.create(name="Active Customer", is_active=True)
    Customer.objects.create(name="Inactive Customer", is_active=False)

    response = client.get(
        reverse("customer-list"),
        {"is_active": "false"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "Inactive Customer"


@pytest.mark.django_db
def test_customer_ordering(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Customer.objects.create(name="Zebra")
    Customer.objects.create(name="Atlas")

    response = client.get(
        reverse("customer-list"),
        {"ordering": "name"},
    )

    assert response.status_code == status.HTTP_200_OK
    names = [item["name"] for item in response.data["results"]]

    assert names == ["Atlas", "Zebra"]


@pytest.mark.django_db
def test_supplier_search(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Supplier.objects.create(name="Atlas Supplier")
    Supplier.objects.create(name="Other Supplier")

    response = client.get(
        reverse("supplier-list"),
        {"search": "Atlas"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "Atlas Supplier"


@pytest.mark.django_db
def test_supplier_filter_by_active_status(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Supplier.objects.create(name="Active Supplier", is_active=True)
    Supplier.objects.create(name="Inactive Supplier", is_active=False)

    response = client.get(
        reverse("supplier-list"),
        {"is_active": "false"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "Inactive Supplier"
