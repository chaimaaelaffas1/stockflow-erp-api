import pytest

from apps.catalog.models import Category, Product
from apps.core.audit import record_audit
from apps.core.models import AuditLog


@pytest.mark.django_db
def test_admin_can_list_audit_logs(
    api_client_for,
    user_factory,
):
    admin = user_factory(
        role="ADMIN",
    )

    category = Category.objects.create(name="Audit category")

    product = Product.objects.create(
        sku="AUDIT-001",
        name="Audit product",
        category=category,
        unit_price="100.00",
    )

    record_audit(
        user=admin,
        action="product.created",
        obj=product,
        payload={
            "sku": product.sku,
        },
    )

    client = api_client_for(admin)

    response = client.get("/api/v1/dashboard/audit-logs/")

    assert response.status_code == 200

    assert response.data["count"] == 1

    audit = response.data["results"][0]

    assert audit["action"] == "product.created"

    assert audit["object_type"] == "catalog.Product"

    assert audit["object_id"] == product.id

    assert audit["actor_email"] == admin.email


@pytest.mark.django_db
def test_non_admin_cannot_list_audit_logs(
    api_client_for,
    user_factory,
):
    user = user_factory(
        role="VIEWER",
    )

    client = api_client_for(user)

    response = client.get("/api/v1/dashboard/audit-logs/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_audit_log_cannot_be_modified(
    user_factory,
):
    from django.core.exceptions import ValidationError

    user = user_factory()

    category = Category.objects.create(name="Audit category 2")

    product = Product.objects.create(
        sku="AUDIT-002",
        name="Product",
        category=category,
        unit_price="10.00",
    )

    audit = record_audit(
        user=user,
        action="product.created",
        obj=product,
    )

    with pytest.raises(ValidationError):
        audit.delete()


@pytest.mark.django_db
def test_audit_log_cannot_be_updated(
    user_factory,
):
    from django.core.exceptions import ValidationError

    user = user_factory()

    category = Category.objects.create(name="Audit category 3")

    product = Product.objects.create(
        sku="AUDIT-003",
        name="Product",
        category=category,
        unit_price="10.00",
    )

    record_audit(
        user=user,
        action="product.created",
        obj=product,
    )

    with pytest.raises(ValidationError):
        AuditLog.objects.all().update(action="product.deleted")
