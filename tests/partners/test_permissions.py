import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_sales_can_create_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.SALES)
    client = api_client_for(user)

    response = client.post(
        reverse("customer-list"),
        {"name": "Customer from Sales"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_sales_cannot_create_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.SALES)
    client = api_client_for(user)

    response = client.post(
        reverse("supplier-list"),
        {"name": "Supplier from Sales"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_purchaser_can_create_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.PURCHASER)
    client = api_client_for(user)

    response = client.post(
        reverse("supplier-list"),
        {"name": "Supplier from Purchaser"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_purchaser_cannot_create_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.PURCHASER)
    client = api_client_for(user)

    response = client.post(
        reverse("customer-list"),
        {"name": "Customer from Purchaser"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_viewer_cannot_create_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.post(
        reverse("customer-list"),
        {"name": "Customer from Viewer"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_viewer_cannot_create_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.post(
        reverse("supplier-list"),
        {"name": "Supplier from Viewer"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_viewer_can_read_customers(user_factory, api_client_for):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(reverse("customer-list"))

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_viewer_can_read_suppliers(user_factory, api_client_for):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(reverse("supplier-list"))

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_sales_cannot_delete_customer(user_factory, api_client_for):
    from apps.partners.models import Customer

    user = user_factory(role=User.Role.SALES)
    client = api_client_for(user)

    customer = Customer.objects.create(name="Atlas")

    response = client.delete(reverse("customer-detail", kwargs={"pk": customer.pk}))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_purchaser_cannot_delete_supplier(user_factory, api_client_for):
    from apps.partners.models import Supplier

    user = user_factory(role=User.Role.PURCHASER)
    client = api_client_for(user)

    supplier = Supplier.objects.create(name="Supplier Atlas")

    response = client.delete(reverse("supplier-detail", kwargs={"pk": supplier.pk}))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_anonymous_user_cannot_read_customers():
    from rest_framework.test import APIClient

    client = APIClient()

    response = client.get(reverse("customer-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
