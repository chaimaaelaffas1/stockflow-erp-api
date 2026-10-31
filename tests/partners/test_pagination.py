import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.accounts.models import User
from apps.partners.models import Customer, Supplier


@pytest.mark.django_db
def test_customer_pagination(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Customer.objects.bulk_create([Customer(name=f"Customer {i}") for i in range(25)])

    response = client.get(reverse("customer-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20
    assert response.data["next"] is not None


@pytest.mark.django_db
def test_customer_second_page(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Customer.objects.bulk_create([Customer(name=f"Customer {i}") for i in range(25)])

    response = client.get(
        reverse("customer-list"),
        {"page": 2},
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 5
    assert response.data["previous"] is not None


@pytest.mark.django_db
def test_supplier_pagination(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Supplier.objects.bulk_create([Supplier(name=f"Supplier {i}") for i in range(25)])

    response = client.get(reverse("supplier-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20
