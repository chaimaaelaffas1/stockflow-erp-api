# 11 — Technical decisions, limitations and roadmap

[← 10 Development guide](10-development-guide.md) · [README](../README.md)

This page explains why the code is shaped the way it is, what trade-offs were accepted, and what is missing. Statements about the reasons are inferred from the code and its tests; the repository does not contain written decision records.

## Technical decisions

### 1. Service layer for workflows that change state or stock
**What:** `confirm/ship/cancel` (sales), `place/cancel/receive` (purchasing) and `adjust_stock` (inventory) are plain functions in `services.py`; views only check permissions, call them and serialise the result.
**Why:** The rules involve several tables and must be atomic. Putting them in functions makes them reusable, testable without HTTP (`tests/*/test_*services.py`) and keeps views short.
**Trade-off:** Two places hold rules: serializers validate input shape (for example active customer), services validate state. Simple CRUD resources (partners, catalog, warehouses) deliberately have no service layer.

### 2. One function mutates stock (`apply_stock_change`)
**What:** Locking, invariant checks, level update and ledger insert live together.
**Why:** Guarantees every change is recorded and validated identically; the test `assert_ledger_consistent` can then assert level = Σ movements.
**Trade-off:** The function requires an open transaction (raises `RuntimeError` otherwise), so callers must remember `atomic`.

### 3. Pessimistic row locking on PostgreSQL
**What:** `select_for_update` on orders, order lines and stock levels.
**Why:** Prevents overselling and over-receiving when requests race; simpler to reason about than optimistic retries.
**Alternatives:** Optimistic concurrency with version numbers; serialisable isolation with retries; atomic `UPDATE … WHERE available >= n` statements.
**Trade-off:** Lock contention on hot stock rows; possible lock-order deadlocks between flows that lock in different orders (see Limitations).

### 4. Invariants also in the database
**What:** `CHECK` constraints (`reserved <= on_hand`, quantities ≥ 0, `received <= ordered`) and unique constraints (SKU, idempotency key).
**Why:** Defence in depth; tests prove the database rejects invalid rows even if Python checks are bypassed.

### 5. Reservation model: `reserved` counter, `available` derived
**What:** Confirmation increments `reserved`; `available = on_hand − reserved` is computed, never stored.
**Why:** One source of truth, no drift between stored fields. The stock-level list computes it in SQL to allow filtering.

### 6. Immutable ledger instead of editable history
**What:** `StockMovement` rows are append-only (application-level guards).
**Why:** Auditability and reconciliation. **Trade-off:** Corrections are made by new movements (adjustments), never by editing history; the guards are not database triggers.

### 7. Idempotent goods receipts
**What:** Client-supplied UUID `idempotency_key`, SHA-256 hash of the normalised payload, unique (`purchase_order`, `idempotency_key`).
**Why:** Network retries must not double stock. Same key and payload returns the original receipt (HTTP 200); same key with a different payload is a 409 conflict.
**Trade-off:** Clients must generate and persist keys. Idempotency exists only for receipts, not for other POST endpoints.

### 8. HTTP 400 vs 409
**What:** Validation problems return 400; valid requests refused by the current state (`invalid_transition`, `insufficient_stock`, `over_receipt`, `resource_in_use`, …) return 409 with a stable `code`.
**Why:** Lets clients distinguish "fix your request" from "state changed, refresh".

### 9. Frozen sales prices
**What:** Line `unit_price` is `NULL` in drafts and copied from the product at confirmation.
**Why:** Later price changes must not alter a confirmed order. **Trade-off:** Drafts show no totals.

### 10. JWT with short-lived access tokens and rotating, blacklisted refresh tokens
**Why:** Stateless API authentication with the ability to revoke refresh tokens (logout, rotation). **Trade-off:** The refresh token is in the JSON body, and access tokens cannot be revoked before they expire (15 minutes).

### 11. Role-based access by action, no object-level permissions
**Why:** Single-company scope; simple, testable matrix ([05](05-authentication-and-permissions.md)). **Trade-off:** Any permitted user can act on every instance of a resource type.

### 12. Soft deactivation instead of deletion for master data
**What:** Customers, suppliers, products and warehouses have `is_active`; products and warehouses have no delete route; FKs use `PROTECT`.
**Why:** Preserve history and references.

### 13. Tooling
PostgreSQL in tests (not SQLite) because locking and constraint behaviour is part of what is being tested; Ruff for lint and format in a single fast tool; GitHub Actions running lint, migration check, tests and OpenAPI validation.

## Known limitations

| Area | Limitation |
|---|---|
| Functional | No invoicing/payments, customer returns, warehouse transfers, lots/serials, multi-currency, multi-company |
| Stock valuation | Dashboard value = `on_hand × current list price`; no FIFO/average cost |
| Audit | Only sales-order and purchase-order events are logged (`create/update/delete/confirm/ship/cancel` for sales; `create/place/cancel/receive` for purchasing). Not logged: stock adjustments, user and role changes, catalog and partner edits, purchase-order update/delete |
| Immutability | Application-level only; `bulk_create` and raw SQL are not guarded |
| Concurrency | Evidence comes from four thread-based tests. Receipts lock stock levels in order-line order, sales in product order; a cross-flow deadlock is theoretically possible and untested. Deadlock errors are not specially handled |
| Security | Refresh token returned in the body; no MFA, lockout or password reset; throttling counters are per process (default local-memory cache); CORS headers not sent (`corsheaders` installed but middleware not enabled) |
| Deployment | The `prod` image needs `DJANGO_SETTINGS_MODULE=config.settings.prod` set at runtime, otherwise `config.settings.dev` (`DEBUG = True`) is used; `migrate` runs at every container start; 3 gunicorn workers are hard-coded; no deployment target, backups, monitoring or structured logging; the prod target was not exercised in verification |
| Dependencies | `requirements/*.txt` are mostly unpinned (only Django is range-pinned), so builds are not reproducible; `dev-installed-packages.txt` is a stale UTF-16 snapshot of older versions (for example Django 5.2.18) |
| API | No filters on the purchase-order list; warehouse list has no explicit ordering; `created_at__gte` is passed to the ORM without explicit validation (behaviour for malformed dates not verified) |
| Swagger UI | Loads assets from a CDN, so it needs internet access |
| Admin site | Only catalog and purchasing models are registered |
| Tests | 86 % statement coverage (2026-11-16), lowest in `accounts/serializers.py`, `inventory/views.py`, `purchasing/views.py`; `seed_demo` untested; no coverage gate in CI; no load or performance tests |

## Inconsistencies found during the documentation audit

These are differences between parts of the repository or between code and the author's original design notes (the planning documents the project was built from are not part of the repository). The code is the reference used in this documentation; none of these were changed.

| # | Finding | Where |
|---|---|---|
| 1 | Planned audit of stock adjustments and role changes (user story "Audit") is **not implemented**; verified live: the audit log held 7 entries after a run that included an adjustment, none for it | `inventory/services.py`, `accounts/` |
| 2 | Planned error codes `inactive_resource` and `duplicate_receipt` do not exist; inactive resources raise `business_rule_violation`/`invalid_transition`, and a replayed receipt is a normal 200 response | `core/exceptions.py`, `purchasing/services.py` |
| 3 | Deleting a used category returns `{"code", "detail"}` instead of the standard `{"error": {...}}` envelope (a custom `destroy` catches `ProtectedError` before the global handler) | `catalog/views.py` |
| 4 | Customer/supplier `destroy` overrides are present only as commented-out code in `partners/viewsets.py`; the behaviour comes from the global `ProtectedError` handler (test `test_delete_customer` covers deletion of an unused customer; no test covers the 409 for a customer or supplier that has orders) | `partners/viewsets.py` |
| 5 | `POST /purchasing/purchase-orders/` is documented in the OpenAPI schema as returning the read representation, but the actual 201 body is the write serializer (`id`, `supplier`, `warehouse`, `lines` only) | `purchasing/views.py` |
| 6 | 404 responses use `code: "request_error"` instead of a `not_found` code (the handler reads `default_code` from Django's `Http404`, which has none) | `core/handlers.py` |
| 7 | Dockerfile prod CMD relies on `DJANGO_SETTINGS_MODULE=config.settings.prod`, which is not set in the image | `Dockerfile`, `manage.py`, `wsgi.py` |
| 8 | Design notes mention a Postman collection; none is in the repository | — |
| 9 | `factory-boy` and `pytest-repeat` are installed for development but unused by the tests | `requirements/dev.txt` |
| 10 | `config/settings/base.py` lists `corsheaders` but never enables it | `config/settings/base.py` |
| 11 | `pre-commit` pins Ruff `v0.14.0` while the dev requirements install the latest Ruff | `.pre-commit-config.yaml`, `requirements/dev.txt` |
| 12 | Coverage targets stated in the original design notes (80 % overall) are met in the measured run (86 %), but nothing in the repository enforces them | — |

## Possible future improvements

Roughly in order of value for this codebase:

1. Audit coverage for stock adjustments, user/role changes and catalog edits (an `AuditLog` helper already exists).
2. Align the error envelope everywhere (category delete, 404 code) and the purchase-order create response with its OpenAPI description.
3. Set `DJANGO_SETTINGS_MODULE` in the `prod` image, pin dependencies (lock file) and add a coverage threshold and Docker build to CI.
4. Use a shared cache (for example Redis) for throttling; configure CORS if a browser front-end is added; move the refresh token to an HttpOnly cookie.
5. Warehouse transfers and customer returns (new movement types, ordered locking).
6. Cost-based stock valuation and invoicing.
7. Object-level permissions (for example sales users limited to their own orders).
8. Observability: structured logs, metrics, error tracking.
