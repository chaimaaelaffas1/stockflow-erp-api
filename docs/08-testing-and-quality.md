# 08 — Testing and quality

[← 07 Inventory and stock management](07-inventory-and-stock-management.md) · [README](../README.md) · Next: [09 Docker and local development](09-docker-and-local-development.md)

## Verification status

The figures below were measured on **2026-11-16** by running the commands in this document with Docker Compose on the author's machine (Python 3.12.16, Django 5.2.19, pytest 9.2.0, PostgreSQL 16). They describe that run, not a guarantee for other commits.

| Check | Result |
|---|---|
| `pytest` | 183 collected, **183 passed** in 11.27 s |
| Coverage (`--cov=apps`) | **86 %** — 1,517 statements, 209 missed |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 123 files already formatted |
| `manage.py check` | No issues |
| `makemigrations --check --dry-run` | No changes detected |



## Test structure

Tests live in `tests/` and mirror the apps. `pytest.ini` selects `config.settings.test` and files named `test_*.py`, and registers the marker `slow` (concurrency tests).

| Directory | Tests | Focus |
|---|---:|---|
| `tests/accounts/` | 39 | Login, refresh rotation, logout, `/me/`, user management permissions, role permission matrix, anonymous access |
| `tests/catalog/` | 31 | Categories and products CRUD, SKU rules, filters/search/ordering, permissions, query count (join) |
| `tests/partners/` | 35 | Customers and suppliers CRUD, filters, pagination, permissions |
| `tests/inventory/` | 24 | Model constraints, stock services, adjustment serializer, views, ledger invariant |
| `tests/sales/` | 29 | Service transitions, API permissions and transitions, **concurrency** |
| `tests/purchasing/` | 17 | Place/cancel/receive services, idempotency, permissions, **concurrency** |
| `tests/core/` | 7 | Audit logs, dashboard, health check, error handler |
| `tests/test_smoke.py` | 1 | Asserts the database vendor is PostgreSQL |

Shared fixtures: `tests/conftest.py` (category, product, warehouse, `user_factory`, `api_client_for` which authenticates by minting a JWT directly), `tests/sales/conftest.py` (role users, customer, stock level, `sales_order_factory`, authenticated clients), `tests/purchasing/conftest.py` (supplier, purchaser, stock manager, purchase order with one line). `tests/helpers.py` provides `assert_ledger_consistent`. Fixtures are hand-written; `factory-boy` is in `requirements/dev.txt` but not used.

## Running the tests

Tests require PostgreSQL and a `SECRET_KEY` and `DATABASE_URL` in the environment (read from `.env`).

```bash
# Docker (recommended)
docker compose run --rm api pytest -q
docker compose run --rm api pytest -q --cov=apps --cov-report=term
docker compose run --rm api pytest tests/sales -q
docker compose run --rm api pytest -m slow -q          # concurrency tests only
docker compose run --rm api pytest -m "not slow" -q    # skip them

# Local virtualenv (PostgreSQL reachable through DATABASE_URL)
pytest -q
```

The database user must be allowed to create the test database (`test_<name>`); the `postgres` Docker image's `POSTGRES_USER` is a superuser. The test settings use the fast MD5 password hasher.

## Important test scenarios

| Area | Scenarios covered (test names) |
|---|---|
| Authentication | `test_login_returns_access_and_refresh`, `test_login_wrong_password_returns_401`, `test_inactive_user_cannot_login`, `test_expired_access_token_is_rejected`, `test_refresh_rotation_invalidates_old_refresh`, `test_logout_blacklists_refresh` |
| Permissions | Parametrised role matrix on 5 create endpoints; 12 endpoints require authentication; viewer/sales/purchaser restrictions in partners, catalog, sales, purchasing, inventory; admin-only users and audit logs |
| Business rules | Confirm reserves stock; all-or-nothing rollback on insufficient stock; price frozen at confirmation; ship decreases `on_hand` and `reserved`; cancel releases reservation; forbidden transitions (ship draft, cancel shipped, confirm twice); inactive customer rejected |
| Purchasing | Partial and complete receipts; over-receipt rejected; idempotent replay; same key with different payload rejected; duplicate lines aggregated; receiving a cancelled order rejected; cancel after partial receipt rejected; receipt creates the stock level |
| Inventory | Negative `on_hand`/`reserved` and `reserved > on_hand` rejected by the database; one stock level per pair; movements immutable; adjustment requires a reason, cannot be zero, cannot go below reserved; ledger equals stock levels |
| Concurrency | Four thread-based tests described in [07](07-inventory-and-stock-management.md#concurrency-and-locking) |
| Quality of queries | `test_product_list_uses_join_for_category` checks the product list does not issue one query per row |
| API conventions | Pagination, filters/search/ordering, unexpected exceptions logged and not exposed (`test_unexpected_exception_is_logged_and_not_exposed`) |

## Coverage

Configuration: none. `pytest-cov` is installed and was run on demand with `--cov=apps`; there is no `.coveragerc`, no `[tool.coverage]` section and no `--cov-fail-under` threshold, and CI does not collect coverage.

Per-module results from the 2026-11-16 run (statements / missed / cover):

| Module | Cover | Comment |
|---|---:|---|
| `inventory/services.py` | 94 % (32/2) | Core stock logic |
| `sales/services.py` | 92 % (63/5) | |
| `purchasing/services.py` | 85 % (99/15) | |
| `sales/views.py` | 100 % | |
| `partners/viewsets.py` | 100 % | |
| `accounts/permissions.py` | 100 % | |
| `core/views.py` | 93 % (58/4) | |
| `core/handlers.py` | 93 % | |
| `inventory/views.py` | 68 % (76/24) | Parts of the stock-level and movement filters untested |
| `purchasing/views.py` | 68 % (73/23) | Several actions are tested at service level rather than through HTTP |
| `purchasing/serializers.py` | 76 % (96/23) | |
| `accounts/serializers.py` | 65 % (49/17) | Last-admin rule and update paths |
| `accounts/models.py` | 77 % (35/8) | |
| `core/management/commands/seed_demo.py` | 0 % (46/46) | No test |
| **Total** | **86 %** | Includes migrations (counted as covered) and empty `tests.py` stubs |

Because migrations and empty files count as covered, the figure slightly flatters the business-logic coverage; the per-module table is more informative.

## Linting and formatting

Configured in `pyproject.toml`: Ruff, `line-length = 88`, `target-version = "py312"`, rule sets `E`, `F`, `I` (import order), `UP`; `F403` ignored (star imports in settings); `migrations` and `.venv` excluded.

```bash
docker compose run --rm api ruff check .
docker compose run --rm api ruff format --check .   # or `ruff format .` to fix
```

## Pre-commit

`.pre-commit-config.yaml` defines: `ruff` (with `--fix`) and `ruff-format` (pinned `v0.14.0`), plus `check-added-large-files`, `detect-private-key` and `end-of-file-fixer`. Enable locally with:

```bash
pip install -r requirements/dev.txt
pre-commit install
pre-commit run --all-files
```

Ruff is not pinned in `requirements/dev.txt`, so the pre-commit Ruff (0.14.0) and the one installed in the image (0.17.5 on 2026-11-16) can differ.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests, with a PostgreSQL 16 service container and Python 3.12:

1. `ruff check .`
2. `ruff format --check .`
3. `python manage.py makemigrations --check --dry-run`
4. `pytest -q` (includes the `slow` concurrency tests)
5. `python manage.py spectacular --file /tmp/schema.yml --validate`

CI does not build the Docker image, measure coverage or deploy.
