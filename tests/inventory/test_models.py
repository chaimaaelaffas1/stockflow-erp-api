import pytest

from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.db import IntegrityError, transaction

from apps.catalog.models import Product
from apps.inventory.models import StockLevel, StockMovement


@pytest.mark.django_db
def test_on_hand_cannot_be_negative(product, warehouse):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockLevel.objects.create(
                product=product,
                warehouse=warehouse,
                on_hand="-1.000",
                reserved="0.000",
            )


@pytest.mark.django_db
def test_reserved_cannot_be_negative(product, warehouse):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockLevel.objects.create(
                product=product,
                warehouse=warehouse,
                on_hand="5.000",
                reserved="-1.000",
            )


@pytest.mark.django_db
def test_reserved_cannot_exceed_on_hand(product, warehouse):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockLevel.objects.create(
                product=product,
                warehouse=warehouse,
                on_hand="5.000",
                reserved="6.000",
            )


@pytest.mark.django_db
def test_product_sku_is_case_insensitive(category):
    Product.objects.create(
        sku="KB-001",
        name="Clavier",
        category=category,
        unit_price="250.00",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Product.objects.create(
                sku="kb-001",
                name="Autre clavier",
                category=category,
                unit_price="200.00",
            )


@pytest.mark.django_db
def test_product_with_stock_cannot_be_deleted(product, warehouse):
    StockLevel.objects.create(
        product=product,
        warehouse=warehouse,
        on_hand="5.000",
        reserved="0.000",
    )

    with pytest.raises(ProtectedError):
        product.delete()


@pytest.mark.django_db
def test_only_one_stock_level_per_product_and_warehouse(
    product,
    warehouse,
):
    StockLevel.objects.create(
        product=product,
        warehouse=warehouse,
        on_hand="10.000",
        reserved="0.000",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockLevel.objects.create(
                product=product,
                warehouse=warehouse,
                on_hand="5.000",
                reserved="0.000",
            )


@pytest.mark.django_db
def test_stock_movement_cannot_be_modified(product, warehouse, user):
    movement = StockMovement.objects.create(
        product=product,
        warehouse=warehouse,
        movement_type=StockMovement.MovementType.RECEIPT,
        on_hand_delta="10.000",
        reserved_delta="0.000",
        reference="TEST-RECEIPT-001",
        created_by=user,
    )

    movement.on_hand_delta = "20.000"

    with pytest.raises(PermissionDenied):
        movement.save()


@pytest.mark.django_db
def test_reorder_level_cannot_be_negative(category):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Product.objects.create(
                sku="REORDER-001",
                name="Product with an invalid threshold",
                category=category,
                unit_price="10.00",
                reorder_level="-1.000",
            )
