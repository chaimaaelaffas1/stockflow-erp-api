from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.inventory.models import StockLevel
from apps.partners.models import Customer
from apps.sales.models import SalesOrder, SalesOrderLine

User = get_user_model()


# --------------------------------------------------
# USERS
# --------------------------------------------------


@pytest.fixture
def sales_user(user_factory):
    return user_factory(
        email="sales@atlas.ma",
        role=User.Role.SALES,
    )


@pytest.fixture
def stock_manager(user_factory):
    return user_factory(
        email="stock-manager@atlas.ma",
        role=User.Role.STOCK_MANAGER,
    )


@pytest.fixture
def admin_user(user_factory):
    return user_factory(
        email="admin@atlas.ma",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def viewer_user(user_factory):
    return user_factory(
        email="viewer@atlas.ma",
        role=User.Role.VIEWER,
    )


# --------------------------------------------------
# CUSTOMER
# --------------------------------------------------


@pytest.fixture
def customer(db):
    return Customer.objects.create(
        name="Client test",
        email="client-test@atlas.ma",
        phone="0600000000",
        address="Marrakech",
    )


# --------------------------------------------------
# STOCK
# --------------------------------------------------


@pytest.fixture
def stock_level(db, product, warehouse):

    return StockLevel.objects.create(
        product=product,
        warehouse=warehouse,
        on_hand=Decimal("10.000"),
        reserved=Decimal("0.000"),
    )


# --------------------------------------------------
# FACTORY FOR ORDERS
# --------------------------------------------------


@pytest.fixture
def sales_order_factory(
    db,
    customer,
    warehouse,
    product,
    sales_user,
):

    def make_order(
        quantity="2.000",
        with_lines=True,
        order_user=None,
        order_customer=None,
        order_warehouse=None,
        order_product=None,
    ):

        order = SalesOrder.objects.create(
            customer=order_customer or customer,
            warehouse=order_warehouse or warehouse,
            created_by=order_user or sales_user,
            notes="Commande de test",
        )

        order.number = f"SO-{order.pk:06d}"
        order.save(update_fields=["number"])

        if with_lines:
            SalesOrderLine.objects.create(
                order=order,
                product=order_product or product,
                quantity=Decimal(quantity),
            )

        return order

    return make_order


# --------------------------------------------------
# AUTHENTICATED API CLIENTS
# --------------------------------------------------


@pytest.fixture
def sales_api_client(api_client_for, sales_user):
    return api_client_for(sales_user)


@pytest.fixture
def stock_api_client(api_client_for, stock_manager):
    return api_client_for(stock_manager)


@pytest.fixture
def admin_api_client(api_client_for, admin_user):
    return api_client_for(admin_user)


@pytest.fixture
def viewer_api_client(api_client_for, viewer_user):
    return api_client_for(viewer_user)
