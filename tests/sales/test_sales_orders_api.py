from decimal import Decimal

import pytest
from django.urls import reverse

from apps.sales.models import SalesOrder

# ==================================================
# 1. CRÉATION D'UNE COMMANDE
# ==================================================


@pytest.mark.django_db
class TestSalesOrderCreateAPI:
    def test_sales_user_can_create_order(
        self,
        sales_api_client,
        customer,
        warehouse,
        product,
    ):
        """
        Un utilisateur SALES peut créer une commande DRAFT.
        """

        url = reverse("sales-order-list")

        data = {
            "customer": customer.pk,
            "warehouse": warehouse.pk,
            "notes": "Commande créée par API",
            "lines": [
                {
                    "product": product.pk,
                    "quantity": "2.000",
                }
            ],
        }

        response = sales_api_client.post(
            url,
            data,
            format="json",
        )

        assert response.status_code == 201

        assert response.data["status"] == "DRAFT"

        assert response.data["number"].startswith("SO-")

        assert len(response.data["lines"]) == 1

        order = SalesOrder.objects.get(
            pk=response.data["id"],
        )

        assert order.customer == customer
        assert order.warehouse == warehouse

        assert order.lines.count() == 1

    def test_viewer_cannot_create_order(
        self,
        viewer_api_client,
        customer,
        warehouse,
        product,
    ):
        """
        Un utilisateur VIEWER ne peut pas créer une commande.
        """

        url = reverse("sales-order-list")

        data = {
            "customer": customer.pk,
            "warehouse": warehouse.pk,
            "lines": [
                {
                    "product": product.pk,
                    "quantity": "2.000",
                }
            ],
        }

        response = viewer_api_client.post(
            url,
            data,
            format="json",
        )

        assert response.status_code == 403

        assert SalesOrder.objects.count() == 0

    def test_cannot_create_order_with_inactive_customer(
        self,
        sales_api_client,
        customer,
        warehouse,
        product,
    ):
        """
        Un client désactivé ne peut pas recevoir une commande.
        """

        customer.is_active = False
        customer.save(update_fields=["is_active"])

        url = reverse("sales-order-list")

        data = {
            "customer": customer.pk,
            "warehouse": warehouse.pk,
            "lines": [
                {
                    "product": product.pk,
                    "quantity": "2.000",
                }
            ],
        }

        response = sales_api_client.post(
            url,
            data,
            format="json",
        )

        assert response.status_code == 400


# ==================================================
# 2. LISTE ET DÉTAIL DES COMMANDES
# ==================================================


@pytest.mark.django_db
class TestSalesOrderReadAPI:
    def test_viewer_can_list_orders(
        self,
        viewer_api_client,
        sales_order_factory,
    ):
        """Un utilisateur VIEWER peut consulter les commandes."""

        order = sales_order_factory()

        url = reverse("sales-order-list")

        response = viewer_api_client.get(url)

        assert response.status_code == 200

        # Compatible avec une réponse paginée ou non paginée.
        results = response.data.get("results", response.data)

        returned_ids = [item["id"] for item in results]

        assert order.pk in returned_ids

    def test_viewer_can_retrieve_order(
        self,
        viewer_api_client,
        sales_order_factory,
    ):
        """
        Un utilisateur VIEWER peut consulter une commande précise.
        """

        order = sales_order_factory()

        url = reverse(
            "sales-order-detail",
            kwargs={"pk": order.pk},
        )

        response = viewer_api_client.get(url)

        assert response.status_code == 200

        assert response.data["id"] == order.pk

        assert response.data["status"] == "DRAFT"


# ==================================================
# 3. CONFIRMATION DEPUIS L'API
# ==================================================


@pytest.mark.django_db
class TestSalesOrderConfirmAPI:
    def test_sales_user_can_confirm_order(
        self,
        sales_api_client,
        sales_order_factory,
        stock_level,
    ):
        """
        Un utilisateur SALES peut confirmer une commande.
        """

        order = sales_order_factory(quantity="3.000")

        url = reverse(
            "sales-order-confirm",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.post(
            url,
            {},
            format="json",
        )

        assert response.status_code == 200

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert order.status == SalesOrder.Status.CONFIRMED

        assert stock_level.reserved == Decimal("3.000")

    def test_confirmation_fails_when_stock_is_insufficient(
        self,
        sales_api_client,
        sales_order_factory,
        stock_level,
    ):
        """
        L'API doit refuser la confirmation si le stock est insuffisant.
        """

        order = sales_order_factory(quantity="20.000")

        url = reverse(
            "sales-order-confirm",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.post(
            url,
            {},
            format="json",
        )

        assert response.status_code == 409

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert order.status == SalesOrder.Status.DRAFT
        assert stock_level.reserved == Decimal("0.000")


# ==================================================
# 4. EXPÉDITION DEPUIS L'API
# ==================================================


@pytest.mark.django_db
class TestSalesOrderShipAPI:
    def test_stock_manager_can_ship_order(
        self,
        stock_api_client,
        sales_order_factory,
        sales_user,
        stock_level,
    ):
        """
        Un STOCK_MANAGER peut expédier une commande confirmée.
        """

        order = sales_order_factory(quantity="2.000")

        # Préparer une commande confirmée.
        from apps.sales.services import confirm_sales_order

        confirm_sales_order(order.pk, sales_user)

        url = reverse(
            "sales-order-ship",
            kwargs={"pk": order.pk},
        )

        response = stock_api_client.post(
            url,
            {},
            format="json",
        )

        assert response.status_code == 200

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert order.status == SalesOrder.Status.SHIPPED

        assert stock_level.on_hand == Decimal("8.000")
        assert stock_level.reserved == Decimal("0.000")

    def test_sales_user_cannot_ship_order(
        self,
        sales_api_client,
        sales_order_factory,
        sales_user,
        stock_level,
    ):
        """
        Un utilisateur SALES ne peut pas expédier une commande.
        """

        from apps.sales.services import confirm_sales_order

        order = sales_order_factory(quantity="2.000")

        confirm_sales_order(order.pk, sales_user)

        url = reverse(
            "sales-order-ship",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.post(
            url,
            {},
            format="json",
        )

        assert response.status_code == 403

        order.refresh_from_db()

        assert order.status == SalesOrder.Status.CONFIRMED


# ==================================================
# 5. ANNULATION DEPUIS L'API
# ==================================================


@pytest.mark.django_db
class TestSalesOrderCancelAPI:
    def test_sales_user_can_cancel_draft_order(
        self,
        sales_api_client,
        sales_order_factory,
    ):
        """
        Un utilisateur SALES peut annuler une commande DRAFT.
        """

        order = sales_order_factory()

        url = reverse(
            "sales-order-cancel",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.post(
            url,
            {},
            format="json",
        )

        assert response.status_code == 200

        order.refresh_from_db()

        assert order.status == SalesOrder.Status.CANCELLED

    def test_sales_user_can_cancel_confirmed_order(
        self,
        sales_api_client,
        sales_order_factory,
        sales_user,
        stock_level,
    ):
        """
        L'annulation d'une commande confirmée doit libérer le stock.
        """

        from apps.sales.services import confirm_sales_order

        order = sales_order_factory(quantity="3.000")

        confirm_sales_order(order.pk, sales_user)

        url = reverse(
            "sales-order-cancel",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.post(
            url,
            {},
            format="json",
        )

        assert response.status_code == 200

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert order.status == SalesOrder.Status.CANCELLED

        assert stock_level.on_hand == Decimal("10.000")
        assert stock_level.reserved == Decimal("0.000")

    def test_cannot_cancel_shipped_order_from_api(
        self,
        sales_api_client,
        sales_order_factory,
        sales_user,
        stock_level,
    ):
        """
        L'API doit refuser l'annulation d'une commande expédiée.
        """

        from apps.sales.services import (
            confirm_sales_order,
            ship_sales_order,
        )

        order = sales_order_factory(quantity="2.000")

        confirm_sales_order(order.pk, sales_user)
        ship_sales_order(order.pk, sales_user)

        url = reverse(
            "sales-order-cancel",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.post(
            url,
            {},
            format="json",
        )

        assert response.status_code == 409

        order.refresh_from_db()

        assert order.status == SalesOrder.Status.SHIPPED


# ==================================================
# 6. MODIFICATION ET SUPPRESSION
# ==================================================


@pytest.mark.django_db
class TestSalesOrderUpdateAPI:
    def test_sales_user_can_update_draft_order(
        self,
        sales_api_client,
        sales_order_factory,
    ):
        """
        Une commande DRAFT peut être modifiée.
        """

        order = sales_order_factory()

        url = reverse(
            "sales-order-detail",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.patch(
            url,
            {"notes": "Nouvelle note"},
            format="json",
        )

        assert response.status_code == 200

        order.refresh_from_db()

        assert order.notes == "Nouvelle note"

    def test_cannot_update_confirmed_order(
        self,
        sales_api_client,
        sales_order_factory,
        sales_user,
        stock_level,
    ):
        """
        Une commande CONFIRMED ne peut plus être modifiée.
        """

        from apps.sales.services import confirm_sales_order

        order = sales_order_factory(quantity="2.000")

        confirm_sales_order(order.pk, sales_user)

        url = reverse(
            "sales-order-detail",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.patch(
            url,
            {"notes": "Modification interdite"},
            format="json",
        )

        assert response.status_code == 409

        order.refresh_from_db()

        assert order.notes == "Commande de test"

    def test_sales_user_can_delete_draft_order(
        self,
        sales_api_client,
        sales_order_factory,
    ):
        """
        Une commande DRAFT peut être supprimée.
        """

        order = sales_order_factory()

        url = reverse(
            "sales-order-detail",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.delete(url)

        assert response.status_code == 204

        assert not SalesOrder.objects.filter(
            pk=order.pk,
        ).exists()

    def test_cannot_delete_confirmed_order(
        self,
        sales_api_client,
        sales_order_factory,
        sales_user,
        stock_level,
    ):
        """
        Une commande CONFIRMED ne peut pas être supprimée.
        """

        from apps.sales.services import confirm_sales_order

        order = sales_order_factory(quantity="2.000")

        confirm_sales_order(order.pk, sales_user)

        url = reverse(
            "sales-order-detail",
            kwargs={"pk": order.pk},
        )

        response = sales_api_client.delete(url)

        assert response.status_code == 409

        assert SalesOrder.objects.filter(
            pk=order.pk,
        ).exists()
