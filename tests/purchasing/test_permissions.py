import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_purchaser_can_create_purchase_order(
    api_client_for,
    user_factory,
    supplier,
    warehouse,
):

    purchaser = user_factory(
        email="purchaser-api@atlas.ma",
        role=User.Role.PURCHASER,
    )

    client = api_client_for(purchaser)

    response = client.post(
        reverse("purchase-order-list"),
        {
            "supplier": supplier.pk,
            "warehouse": warehouse.pk,
            "lines": [],
        },
        format="json",
    )

    assert response.status_code == 201


def test_viewer_cannot_create_purchase_order(
    api_client_for,
    user_factory,
    supplier,
    warehouse,
):

    viewer = user_factory(
        email="viewer-api@atlas.ma",
        role=User.Role.VIEWER,
    )

    client = api_client_for(viewer)

    response = client.post(
        reverse("purchase-order-list"),
        {
            "supplier": supplier.pk,
            "warehouse": warehouse.pk,
            "lines": [],
        },
        format="json",
    )

    assert response.status_code == 403


def test_purchaser_cannot_receive_goods(
    api_client_for,
    purchaser,
    purchase_order,
):

    client = api_client_for(purchaser)

    response = client.post(
        reverse(
            "purchase-order-receive",
            args=[purchase_order.pk],
        ),
        {
            "idempotency_key": "b0d9bdf5-6479-4a7c-93fb-1f92bce1f126",
            "lines": [],
        },
        format="json",
    )

    assert response.status_code == 403
