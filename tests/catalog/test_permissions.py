import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

CATEGORIES_URL = "/api/v1/catalog/categories/"
PRODUCTS_URL = "/api/v1/catalog/products/"


@pytest.mark.django_db
def test_anonymous_user_cannot_list_categories():
    client = APIClient()

    response = client.get(CATEGORIES_URL)

    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_anonymous_user_cannot_list_products():
    client = APIClient()

    response = client.get(PRODUCTS_URL)

    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_sales_can_read_products(
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.SALES)
    client = api_client_for(user)

    response = client.get(PRODUCTS_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_purchaser_can_read_categories(
    user_factory,
    api_client_for,
):
    user = user_factory(role=User.Role.PURCHASER)
    client = api_client_for(user)

    response = client.get(CATEGORIES_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_inactive_user_cannot_read_products(
    user_factory,
    api_client_for,
):
    user = user_factory(
        role=User.Role.VIEWER,
        is_active=False,
    )
    client = api_client_for(user)

    response = client.get(PRODUCTS_URL)

    assert response.status_code == 401
