import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.inventory.models import (
    StockLevel,
    StockMovement,
)

User = get_user_model()


@pytest.mark.django_db
def test_stock_level_list(
    product,
    warehouse,
    user,
    api_client_for,
):

    client = api_client_for(user)
    url = reverse("stock-level-list")
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_stock_adjustment_by_stock_manager(
    product,
    warehouse,
    user_factory,
    api_client_for,
):

    manager = user_factory(role=User.Role.STOCK_MANAGER)

    client = api_client_for(manager)
    url = reverse("stock-adjustments")
    response = client.post(
        url,
        {
            "product": product.id,
            "warehouse": warehouse.id,
            "quantity_delta": "5.000",
            "reason": "Physical correction",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED

    assert StockMovement.objects.count() == 1

    level = StockLevel.objects.get(
        product=product,
        warehouse=warehouse,
    )

    assert level.on_hand == 5


@pytest.mark.django_db
def test_stock_adjustment_forbidden_for_viewer(
    product,
    warehouse,
    user_factory,
    api_client_for,
):

    viewer = user_factory(role=User.Role.VIEWER)

    client = api_client_for(viewer)
    url = reverse("stock-adjustments")
    response = client.post(
        url,
        {
            "product": product.id,
            "warehouse": warehouse.id,
            "quantity_delta": "5.000",
            "reason": "Physical correction",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN

    assert StockMovement.objects.count() == 0


@pytest.mark.django_db
def test_stock_movement_is_read_only(
    product,
    warehouse,
    user,
    api_client_for,
):

    client = api_client_for(user)
    url = reverse("stock-movement-list")
    response = client.post(
        url,
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
