# 10 — Development guide

[← 09 Docker and local development](09-docker-and-local-development.md) · [README](../README.md) · Next: [11 Technical decisions](11-technical-decisions.md)

This guide shows how to extend the project following the patterns already used in the code. Commands assume the Docker setup from [09](09-docker-and-local-development.md); drop the `docker compose exec api` / `run --rm api` prefix in a local virtualenv. Remember to rebuild the image after code changes (`docker compose up -d --build`).

## Coding conventions observed in the codebase

| Topic | Convention |
|---|---|
| Layout | One Django app per business area under `apps/`; app config `name = "apps.<name>"` |
| Models | Extend `apps.core.models.TimestampedModel` (`created_at`, `updated_at`); name constraints explicitly (`uniq_…`, `…_gte_0`); quantities `DecimalField(12, 3)`, money `DecimalField(12, 2)`; `on_delete=PROTECT` for references, `CASCADE` only for owned lines |
| Serializers | List fields explicitly (no `__all__`); mark server-controlled fields in `read_only_fields`; normalise input in `validate_<field>` |
| Views | `ViewSet` per resource; permissions chosen in `get_permissions()` by `self.action`; restrict verbs with `http_method_names` when a verb must not exist; `select_related`/`prefetch_related` in querysets |
| Business logic | In `services.py`, keyword-only arguments, `transaction.atomic`, lock rows with `select_for_update`, raise `BusinessRuleError` subclasses, write audit entries with `record_audit` |
| Errors | Never build error responses by hand in new code; raise DRF `ValidationError` (400) or a `BusinessRuleError` (409) and let `api_exception_handler` format it |
| API docs | `@extend_schema` / `@extend_schema_view` with a `tags` entry and a short description on every endpoint |
| Style | Ruff (`E`, `F`, `I`, `UP`), line length 88, `ruff format`; imports sorted |
| Tests | One test module per concern under `tests/<app>/`, named `test_*.py` |

Existing code contains some French comments and docstrings; new documentation and code comments should be in English.

## Add a new Django app

```bash
mkdir apps/shipping
docker compose exec api python manage.py startapp shipping apps/shipping
```

1. Edit `apps/shipping/apps.py` so that `name = "apps.shipping"`.
2. Register it in `config/settings/base.py` under `LOCAL_APPS`: `"apps.shipping"`.
3. Create `apps/shipping/urls.py` (a `DefaultRouter`) and include it in `config/urls.py`: `path("api/v1/shipping/", include("apps.shipping.urls"))`.
4. Add `tests/shipping/__init__.py` and tests.
5. Generate and commit migrations (next section).

## Add a model

```python
# apps/shipping/models.py
from django.db import models
from django.db.models import Q
from apps.core.models import TimestampedModel

class Carrier(TimestampedModel):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(name=""), name="carrier_name_not_empty"),
        ]
```

```bash
docker compose exec api python manage.py makemigrations shipping
docker compose exec api python manage.py migrate
docker compose exec api python manage.py makemigrations --check --dry-run   # must report no changes (CI does this)
```

Commit the generated migration. Register the model in `admin.py` if you want it in the Django admin (currently only catalog and purchasing models are registered).

## Create an API endpoint

1. **Serializer** in `serializers.py` with explicit `fields` and `read_only_fields`.
2. **ViewSet** in `views.py`:

```python
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema_view, extend_schema
from apps.accounts.models import User
from apps.accounts.permissions import HasAnyRole

@extend_schema_view(list=extend_schema(tags=["Shipping - Carriers"], summary="List carriers"))
class CarrierViewSet(ModelViewSet):
    queryset = Carrier.objects.all().order_by("name")
    serializer_class = CarrierSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        return [HasAnyRole(User.Role.ADMIN, User.Role.STOCK_MANAGER, read_for_all=True)()]
```

3. **Route** it in `urls.py`: `router.register("carriers", CarrierViewSet, basename="carrier")`.
4. Add filtering/search/ordering with `filterset_fields`, `search_fields`, `ordering_fields` (default backends are already enabled globally).
5. Regenerate the committed schema when the API changes (see below).

Remember that pagination applies automatically to list endpoints, and that an explicit `ordering` on the queryset avoids unordered pagination.

## Add business logic (a service)

Use the sales and purchasing services as templates.

```python
# apps/shipping/services.py
from django.db import transaction
from apps.core.audit import record_audit
from apps.core.exceptions import InvalidTransition
from .models import Shipment

@transaction.atomic
def dispatch_shipment(*, shipment_id, user):
    shipment = Shipment.objects.select_for_update().get(pk=shipment_id)   # 1. lock
    if shipment.status != Shipment.Status.READY:                         # 2. check state
        raise InvalidTransition("Only READY shipments can be dispatched.",
                                {"current_status": shipment.status})
    # 3. change stock only through apply_stock_change(...)
    shipment.status = Shipment.Status.DISPATCHED                          # 4. transition
    shipment.save(update_fields=["status", "updated_at"])
    record_audit(user=user, action="shipment.dispatched", obj=shipment,
                 payload={"number": shipment.number})                    # 5. audit
    return shipment
```

Rules to keep:

- Change stock **only** through `apps.inventory.services.apply_stock_change`, inside a transaction.
- When touching several stock levels, process lines in a deterministic order (for example by `product_id`).
- Raise a `BusinessRuleError` subclass (add a new one in `apps/core/exceptions.py` if you need a new `code`); the handler turns it into HTTP 409.
- Call the service from a thin `@action` view and return a serializer's data.
- Add an audit entry for important state changes (note that stock adjustments currently have none).

## Write tests

- Put tests in `tests/<app>/test_*.py`; use `@pytest.mark.django_db`.
- Create users with `user_factory(role=...)` and authenticate with `api_client_for(user)` (see `tests/conftest.py`).
- Test the happy path, each validation error, **each role** (allowed and forbidden) and every forbidden state transition. Assert the error `code`, not only the status.
- After stock operations call `assert_ledger_consistent()` from `tests/helpers.py`.
- For concurrency, use `@pytest.mark.slow` and `@pytest.mark.django_db(transaction=True)`, open a new connection per thread (`connections.close_all()` at the start and end of the thread function), join threads with a timeout and assert on final database state (see `tests/sales/test_concurrency.py`).

```bash
docker compose run --rm api pytest tests/shipping -q
docker compose run --rm api ruff check . && docker compose run --rm api ruff format --check .
```

## Regenerate the OpenAPI schema

```bash
# Docker: write the schema to stdout and redirect it on the host
docker compose run --rm -T api python manage.py spectacular > schema.yml

# Local virtualenv
python manage.py spectacular --validate --file schema.yml
```

Review the diff before committing. CI only validates the schema (`--validate`); it does not check that the committed `schema.yml` is up to date.

## Pre-merge checklist

1. Ruff lint and format pass; pre-commit hooks pass.
2. `makemigrations --check --dry-run` reports no changes and migrations are committed.
3. All tests pass, including `slow` ones.
4. New endpoints have `@extend_schema` metadata, permissions chosen per action and tests for each role.
5. Documentation in `docs/` is updated when behaviour, endpoints or permissions change.
