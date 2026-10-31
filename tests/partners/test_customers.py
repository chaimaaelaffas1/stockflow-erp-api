import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.accounts.models import User
from apps.partners.models import Customer


@pytest.mark.django_db
def test_create_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        reverse("customer-list"),
        {
            "name": "Atlas Distribution",
            "email": "CONTACT@ATLAS.MA",
            "phone": "0600000000",
            "address": "Marrakech",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Atlas Distribution"
    assert response.data["email"] == "contact@atlas.ma"
    assert Customer.objects.filter(email="contact@atlas.ma").exists()


@pytest.mark.django_db
def test_list_customers(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Customer.objects.create(name="Customer A")
    Customer.objects.create(name="Customer B")

    response = client.get(reverse("customer-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_retrieve_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    customer = Customer.objects.create(name="Atlas")

    response = client.get(reverse("customer-detail", kwargs={"pk": customer.pk}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Atlas"


@pytest.mark.django_db
def test_update_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    customer = Customer.objects.create(name="Old name")

    response = client.put(
        reverse("customer-detail", kwargs={"pk": customer.pk}),
        {
            "name": "New name",
            "email": "new@atlas.ma",
            "phone": "0611111111",
            "address": "Casablanca",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    customer.refresh_from_db()
    assert customer.name == "New name"


@pytest.mark.django_db
def test_partial_update_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    customer = Customer.objects.create(
        name="Atlas",
        phone="0600000000",
    )

    response = client.patch(
        reverse("customer-detail", kwargs={"pk": customer.pk}),
        {"phone": "0611111111"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    customer.refresh_from_db()
    assert customer.phone == "0611111111"
    assert customer.name == "Atlas"


@pytest.mark.django_db
def test_deactivate_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    customer = Customer.objects.create(name="Atlas")

    response = client.patch(
        reverse("customer-detail", kwargs={"pk": customer.pk}),
        {"is_active": False},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    customer.refresh_from_db()
    assert customer.is_active is False


@pytest.mark.django_db
def test_customer_name_cannot_be_empty(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        reverse("customer-list"),
        {"name": "   "},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_delete_customer(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    customer = Customer.objects.create(name="Atlas")

    response = client.delete(reverse("customer-detail", kwargs={"pk": customer.pk}))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Customer.objects.filter(pk=customer.pk).exists()
