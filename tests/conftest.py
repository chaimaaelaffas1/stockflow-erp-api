# Les fixtures permettent de réutiliser les objets nécessaires à plusieurs tests.

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Category, Product
from apps.inventory.models import Warehouse


@pytest.fixture
def category(db):
    return Category.objects.create(name="Outillage test")


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        sku="TEST-001",
        name="Produit test",
        category=category,
        unit_price="100.00",
    )


@pytest.fixture
def warehouse(db):
    return Warehouse.objects.create(
        code="TEST-01",
        name="Entrepôt test",
    )


@pytest.fixture
def user(db):
    User = get_user_model()

    return User.objects.create_user(
        username="test-admin",
        email="test-admin@stockflow.local",
        password="Test-password-123",
    )


@pytest.fixture
def user_factory(db):
    User = get_user_model()

    def make_user(
        email="user@atlas.ma",
        password="Strong-Test-Password-2026!",
        role=User.Role.VIEWER,
        is_active=True,
        username=None,
    ):
        return User.objects.create_user(
            email=email,
            password=password,
            username=username or email,
            role=role,
            is_active=is_active,
        )

    return make_user


@pytest.fixture
def api_client_for():
    def make_client(user):
        client = APIClient()

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        return client

    return make_client
