# Les fixtures permettent de réutiliser les objets nécessaires à plusieurs tests.

import pytest
from django.contrib.auth import get_user_model

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
