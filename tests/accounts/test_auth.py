from datetime import timedelta

import pytest
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import User


pytestmark = pytest.mark.django_db


def test_login_returns_access_and_refresh(user_factory):
    user_factory(
        email="sales@atlas.ma",
        password="Strong-Test-Password-2026!",
        role=User.Role.SALES,
    )

    client = APIClient()

    response = client.post(
        reverse("token_obtain_pair"),
        {
            "email": "sales@atlas.ma",
            "password": "Strong-Test-Password-2026!",
        },
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_login_wrong_password_returns_401(user_factory):
    user_factory(
        email="sales@atlas.ma",
        password="Strong-Test-Password-2026!",
        role=User.Role.SALES,
    )

    client = APIClient()

    response = client.post(
        reverse("token_obtain_pair"),
        {
            "email": "sales@atlas.ma",
            "password": "Wrong-Password!",
        },
        format="json",
    )

    assert response.status_code == 401


def test_inactive_user_cannot_login(user_factory):
    user_factory(
        email="inactive@atlas.ma",
        password="Strong-Test-Password-2026!",
        role=User.Role.SALES,
        is_active=False,
    )

    client = APIClient()

    response = client.post(
        reverse("token_obtain_pair"),
        {
            "email": "inactive@atlas.ma",
            "password": "Strong-Test-Password-2026!",
        },
        format="json",
    )

    assert response.status_code == 401


def test_me_requires_authentication():
    client = APIClient()

    response = client.get(reverse("auth_me"))

    assert response.status_code == 401


def test_me_returns_current_user(user_factory, api_client_for):
    user = user_factory(
        email="sales@atlas.ma",
        role=User.Role.SALES,
    )

    client = api_client_for(user)

    response = client.get(reverse("auth_me"))

    assert response.status_code == 200
    assert response.data["email"] == "sales@atlas.ma"
    assert response.data["role"] == User.Role.SALES
    assert "password" not in response.data


def test_expired_access_token_is_rejected(user_factory):
    user = user_factory(email="expired@atlas.ma")

    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(seconds=-1))

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")

    response = client.get(reverse("auth_me"))

    assert response.status_code == 401


def test_refresh_rotation_invalidates_old_refresh(user_factory):
    user = user_factory(email="refresh@atlas.ma")
    old_refresh = str(RefreshToken.for_user(user))

    client = APIClient()

    first_response = client.post(
        reverse("token_refresh"),
        {"refresh": old_refresh},
        format="json",
    )

    assert first_response.status_code == 200
    assert "access" in first_response.data
    assert "refresh" in first_response.data

    second_response = client.post(
        reverse("token_refresh"),
        {"refresh": old_refresh},
        format="json",
    )

    assert second_response.status_code == 401


def test_logout_blacklists_refresh(user_factory, api_client_for):
    user = user_factory(email="logout@atlas.ma")
    refresh = str(RefreshToken.for_user(user))

    client = api_client_for(user)

    logout_response = client.post(
        reverse("auth_logout"),
        {"refresh": refresh},
        format="json",
    )

    assert logout_response.status_code == 204

    refresh_response = client.post(
        reverse("token_refresh"),
        {"refresh": refresh},
        format="json",
    )

    assert refresh_response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        User.Role.VIEWER,
        User.Role.SALES,
        User.Role.STOCK_MANAGER,
        User.Role.PURCHASER,
    ],
)
def test_non_admin_cannot_list_users(user_factory, api_client_for, role):
    user = user_factory(
        email=f"{role.lower()}@atlas.ma",
        role=role,
    )
    client = api_client_for(user)

    response = client.get(reverse("users-list"))

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role",
    [
        User.Role.VIEWER,
        User.Role.SALES,
        User.Role.STOCK_MANAGER,
        User.Role.PURCHASER,
    ],
)
def test_non_admin_cannot_create_user(user_factory, api_client_for, role):
    user = user_factory(
        email=f"{role.lower()}@atlas.ma",
        role=role,
    )
    client = api_client_for(user)

    response = client.post(
        reverse("users-list"),
        {
            "email": f"new-{role.lower()}@atlas.ma",
            "username": f"new-{role.lower()}@atlas.ma",
            "password": "Strong-New-Password-2026!",
            "role": User.Role.VIEWER,
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 403


def test_admin_can_list_users(user_factory, api_client_for):
    admin = user_factory(
        email="admin-list@atlas.ma",
        role=User.Role.ADMIN,
    )
    client = api_client_for(admin)

    response = client.get(reverse("users-list"))

    assert response.status_code == 200


def test_admin_can_retrieve_user(user_factory, api_client_for):
    admin = user_factory(
        email="admin-detail@atlas.ma",
        role=User.Role.ADMIN,
    )
    target = user_factory(
        email="target@atlas.ma",
        role=User.Role.VIEWER,
    )
    client = api_client_for(admin)

    response = client.get(reverse("users-detail", kwargs={"pk": target.pk}))

    assert response.status_code == 200
    assert response.data["email"] == target.email
    assert "password" not in response.data


def test_non_admin_cannot_retrieve_user(user_factory, api_client_for):
    sales = user_factory(
        email="sales-detail@atlas.ma",
        role=User.Role.SALES,
    )
    target = user_factory(
        email="target-detail@atlas.ma",
        role=User.Role.VIEWER,
    )
    client = api_client_for(sales)

    response = client.get(reverse("users-detail", kwargs={"pk": target.pk}))

    assert response.status_code == 403


def test_admin_can_update_user(user_factory, api_client_for):
    admin = user_factory(
        email="admin-update@atlas.ma",
        role=User.Role.ADMIN,
    )
    target = user_factory(
        email="target-update@atlas.ma",
        role=User.Role.VIEWER,
    )
    client = api_client_for(admin)

    response = client.patch(
        reverse("users-detail", kwargs={"pk": target.pk}),
        {"first_name": "Updated"},
        format="json",
    )

    assert response.status_code == 200

    target.refresh_from_db()
    assert target.first_name == "Updated"


def test_non_admin_cannot_update_user(user_factory, api_client_for):
    sales = user_factory(
        email="sales-update@atlas.ma",
        role=User.Role.SALES,
    )
    target = user_factory(
        email="target-protected@atlas.ma",
        role=User.Role.VIEWER,
    )
    client = api_client_for(sales)

    response = client.patch(
        reverse("users-detail", kwargs={"pk": target.pk}),
        {"first_name": "Unauthorized"},
        format="json",
    )

    assert response.status_code == 403

    target.refresh_from_db()
    assert target.first_name != "Unauthorized"


def test_admin_cannot_delete_user(user_factory, api_client_for):
    admin = user_factory(
        email="admin-delete@atlas.ma",
        role=User.Role.ADMIN,
    )
    target = user_factory(
        email="target-delete@atlas.ma",
        role=User.Role.VIEWER,
    )
    client = api_client_for(admin)

    response = client.delete(reverse("users-detail", kwargs={"pk": target.pk}))

    assert response.status_code == 405

    assert User.objects.filter(pk=target.pk).exists()
