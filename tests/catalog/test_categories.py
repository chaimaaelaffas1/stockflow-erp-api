import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Category

User = get_user_model()

BASE_URL = "/api/v1/catalog/categories/"


@pytest.mark.django_db
def test_admin_can_create_category(user_factory, api_client_for):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {"name": "Informatique"},
        format="json",
    )

    assert response.status_code == 201
    assert Category.objects.filter(name="Informatique").exists()


@pytest.mark.django_db
def test_stock_manager_can_create_category(
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.STOCK_MANAGER)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {"name": "Outillage"},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_viewer_cannot_create_category(
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {"name": "Informatique"},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_authenticated_user_can_list_categories(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.VIEWER)
    client = api_client_for(user)

    response = client.get(BASE_URL)

    assert response.status_code == 200
    assert len(response.data["results"]) >= 1


@pytest.mark.django_db
def test_category_name_is_trimmed(
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {"name": "  Informatique  "},
        format="json",
    )

    assert response.status_code == 201
    assert Category.objects.filter(name="Informatique").exists()


@pytest.mark.django_db
def test_duplicate_category_name_is_rejected(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.post(
        BASE_URL,
        {"name": category.name.upper()},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_stock_manager_cannot_delete_category(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.STOCK_MANAGER)
    client = api_client_for(user)

    response = client.delete(f"{BASE_URL}{category.id}/")

    assert response.status_code == 403
    assert Category.objects.filter(id=category.id).exists()


@pytest.mark.django_db
def test_admin_can_delete_unused_category(
    category,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    response = client.delete(f"{BASE_URL}{category.id}/")

    assert response.status_code == 204
    assert not Category.objects.filter(id=category.id).exists()


@pytest.mark.django_db
def test_admin_gets_409_when_deleting_used_category(
    product,
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.ADMIN)
    client = api_client_for(user)

    category_id = product.category_id

    response = client.delete(f"{BASE_URL}{category_id}/")

    assert response.status_code == 409
    assert Category.objects.filter(id=category_id).exists()
