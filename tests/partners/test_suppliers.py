import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from apps.accounts.models import User
from apps.partners.models import Supplier


@pytest.mark.django_db
def test_create_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        reverse("supplier-list"),
        {
            "name": "Supplier Atlas",
            "email": "CONTACT@SUPPLIER.MA",
            "phone": "0600000000",
            "address": "Marrakech",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Supplier Atlas"
    assert response.data["email"] == "contact@supplier.ma"
    assert Supplier.objects.filter(email="contact@supplier.ma").exists()


@pytest.mark.django_db
def test_list_suppliers(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    Supplier.objects.create(name="Supplier A")
    Supplier.objects.create(name="Supplier B")

    response = client.get(reverse("supplier-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_retrieve_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    supplier = Supplier.objects.create(name="Supplier Atlas")

    response = client.get(reverse("supplier-detail", kwargs={"pk": supplier.pk}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Supplier Atlas"


@pytest.mark.django_db
def test_update_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    supplier = Supplier.objects.create(name="Old supplier")

    response = client.put(
        reverse("supplier-detail", kwargs={"pk": supplier.pk}),
        {
            "name": "New supplier",
            "email": "new@supplier.ma",
            "phone": "0611111111",
            "address": "Casablanca",
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    supplier.refresh_from_db()
    assert supplier.name == "New supplier"


@pytest.mark.django_db
def test_partial_update_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    supplier = Supplier.objects.create(
        name="Supplier Atlas",
        phone="0600000000",
    )

    response = client.patch(
        reverse("supplier-detail", kwargs={"pk": supplier.pk}),
        {"phone": "0611111111"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    supplier.refresh_from_db()
    assert supplier.phone == "0611111111"


@pytest.mark.django_db
def test_deactivate_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    supplier = Supplier.objects.create(name="Supplier Atlas")

    response = client.patch(
        reverse("supplier-detail", kwargs={"pk": supplier.pk}),
        {"is_active": False},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK

    supplier.refresh_from_db()
    assert supplier.is_active is False


@pytest.mark.django_db
def test_supplier_name_cannot_be_empty(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        reverse("supplier-list"),
        {"name": "   "},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_delete_supplier(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    supplier = Supplier.objects.create(name="Supplier Atlas")

    response = client.delete(reverse("supplier-detail", kwargs={"pk": supplier.pk}))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Supplier.objects.filter(pk=supplier.pk).exists()
