from decimal import Decimal

import pytest

from apps.catalog.models import Product
from apps.core.exceptions import (
    BusinessRuleError,
    InsufficientStock,
    InvalidTransition,
)
from apps.inventory.models import StockMovement
from apps.sales.models import SalesOrder
from apps.sales.services import (
    cancel_sales_order,
    confirm_sales_order,
    ship_sales_order,
)


@pytest.mark.django_db
class TestConfirmSalesOrder:
    def test_confirm_draft_order_reserves_stock(
        self,
        sales_order_factory,
        sales_user,
        stock_level,
        product,
        warehouse,
    ):

        order = sales_order_factory(quantity="3.000")

        result = confirm_sales_order(order.pk, sales_user)

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert result.pk == order.pk

        assert order.status == SalesOrder.Status.CONFIRMED
        assert order.confirmed_at is not None

        assert stock_level.on_hand == Decimal("10.000")
        assert stock_level.reserved == Decimal("3.000")
        assert stock_level.available == Decimal("7.000")

        line = order.lines.get()

        assert line.unit_price == product.unit_price

        movement = StockMovement.objects.get(
            reference=order.number,
            movement_type=StockMovement.MovementType.RESERVE,
        )

        assert movement.product == product
        assert movement.warehouse == warehouse

        assert movement.on_hand_delta == Decimal("0")
        assert movement.reserved_delta == Decimal("3.000")

        assert movement.created_by == sales_user

    def test_confirm_order_without_lines_raises_error(
        self,
        sales_order_factory,
        sales_user,
    ):

        order = sales_order_factory(with_lines=False)

        with pytest.raises(BusinessRuleError):
            confirm_sales_order(order.pk, sales_user)

        order.refresh_from_db()

        assert order.status == SalesOrder.Status.DRAFT
        assert order.confirmed_at is None

    def test_confirm_order_with_insufficient_stock_rolls_back_everything(
        self,
        sales_order_factory,
        sales_user,
        product,
        category,
        stock_level,
    ):

        second_product = Product.objects.create(
            sku="TEST-002",
            name="Deuxième produit",
            category=category,
            unit_price=Decimal("50.00"),
        )

        order = sales_order_factory(quantity="3.000")

        order.lines.create(
            product=second_product,
            quantity=Decimal("2.000"),
        )

        with pytest.raises(InsufficientStock):
            confirm_sales_order(order.pk, sales_user)

        stock_level.refresh_from_db()
        order.refresh_from_db()

        assert order.status == SalesOrder.Status.DRAFT

        assert stock_level.reserved == Decimal("0.000")

        for line in order.lines.all():
            assert line.unit_price is None

        assert not StockMovement.objects.filter(
            reference=order.number,
        ).exists()

    def test_cannot_confirm_already_confirmed_order(
        self,
        sales_order_factory,
        sales_user,
        stock_level,
    ):

        order = sales_order_factory(quantity="2.000")

        confirm_sales_order(order.pk, sales_user)

        with pytest.raises(InvalidTransition):
            confirm_sales_order(order.pk, sales_user)

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert order.status == SalesOrder.Status.CONFIRMED

        assert stock_level.reserved == Decimal("2.000")

    def test_price_is_frozen_at_confirmation(
        self,
        sales_order_factory,
        sales_user,
        product,
        stock_level,
    ):

        order = sales_order_factory(quantity="2.000")

        original_price = product.unit_price

        confirm_sales_order(order.pk, sales_user)

        product.unit_price = Decimal("150.00")
        product.save(update_fields=["unit_price"])

        line = order.lines.get()

        line.refresh_from_db()

        assert line.unit_price == original_price
        assert line.unit_price == Decimal("100.00")


@pytest.mark.django_db
class TestShipSalesOrder:
    def test_ship_confirmed_order_decreases_stock(
        self,
        sales_order_factory,
        sales_user,
        stock_level,
    ):

        order = sales_order_factory(quantity="3.000")

        confirm_sales_order(order.pk, sales_user)

        result = ship_sales_order(order.pk, sales_user)

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert result.pk == order.pk

        assert order.status == SalesOrder.Status.SHIPPED
        assert order.shipped_at is not None

        assert stock_level.on_hand == Decimal("7.000")
        assert stock_level.reserved == Decimal("0.000")
        assert stock_level.available == Decimal("7.000")

        movement = StockMovement.objects.get(
            reference=order.number,
            movement_type=StockMovement.MovementType.SHIPMENT,
        )

        assert movement.on_hand_delta == Decimal("-3.000")
        assert movement.reserved_delta == Decimal("-3.000")

        assert movement.created_by == sales_user

    def test_cannot_ship_draft_order(
        self,
        sales_order_factory,
        sales_user,
    ):

        order = sales_order_factory()

        with pytest.raises(InvalidTransition):
            ship_sales_order(order.pk, sales_user)

        order.refresh_from_db()

        assert order.status == SalesOrder.Status.DRAFT

    def test_cannot_ship_already_shipped_order(
        self,
        sales_order_factory,
        sales_user,
        stock_level,
    ):

        order = sales_order_factory(quantity="2.000")

        # Première étape : confirmer la commande.
        confirm_sales_order(order.pk, sales_user)

        # Deuxième étape : expédier la commande.
        ship_sales_order(order.pk, sales_user)

        # Troisième étape : essayer de l'expédier une deuxième fois.
        with pytest.raises(InvalidTransition):
            ship_sales_order(order.pk, sales_user)

        order.refresh_from_db()

        assert order.status == SalesOrder.Status.SHIPPED


@pytest.mark.django_db
class TestCancelSalesOrder:
    def test_cancel_draft_order_without_stock_movement(
        self,
        sales_order_factory,
        sales_user,
        stock_level,
    ):

        order = sales_order_factory(quantity="2.000")

        result = cancel_sales_order(order.pk, sales_user)

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert result.pk == order.pk

        assert order.status == SalesOrder.Status.CANCELLED
        assert order.cancelled_at is not None

        assert stock_level.on_hand == Decimal("10.000")
        assert stock_level.reserved == Decimal("0.000")

        assert not StockMovement.objects.filter(
            reference=order.number,
        ).exists()

    def test_cancel_confirmed_order_releases_reserved_stock(
        self,
        sales_order_factory,
        sales_user,
        stock_level,
    ):

        order = sales_order_factory(quantity="4.000")

        confirm_sales_order(order.pk, sales_user)

        stock_level.refresh_from_db()

        assert stock_level.reserved == Decimal("4.000")

        cancel_sales_order(order.pk, sales_user)

        order.refresh_from_db()
        stock_level.refresh_from_db()

        assert order.status == SalesOrder.Status.CANCELLED
        assert order.cancelled_at is not None

        assert stock_level.on_hand == Decimal("10.000")
        assert stock_level.reserved == Decimal("0.000")

        movement = StockMovement.objects.get(
            reference=order.number,
            movement_type=StockMovement.MovementType.RELEASE,
        )

        assert movement.on_hand_delta == Decimal("0")
        assert movement.reserved_delta == Decimal("-4.000")

        assert movement.reason == "Sales order cancelled"

    def test_cannot_cancel_shipped_order(
        self,
        sales_order_factory,
        sales_user,
        stock_level,
    ):

        order = sales_order_factory(quantity="2.000")

        confirm_sales_order(order.pk, sales_user)

        ship_sales_order(order.pk, sales_user)

        with pytest.raises(InvalidTransition):
            cancel_sales_order(order.pk, sales_user)

        order.refresh_from_db()

        assert order.status == SalesOrder.Status.SHIPPED
