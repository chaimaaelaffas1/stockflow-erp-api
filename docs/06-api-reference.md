# 06 — API reference

[← 05 Authentication and permissions](05-authentication-and-permissions.md) · [README](../README.md) · Next: [07 Inventory and stock management](07-inventory-and-stock-management.md)

The interactive, always-current reference is generated from the code:

| Tool | URL (local) |
|---|---|
| Swagger UI | `http://localhost:8000/api/schema/swagger-ui/` |
| ReDoc | `http://localhost:8000/api/schema/redoc/` |
| OpenAPI schema | `http://localhost:8000/api/schema/` (a copy is committed as `schema.yml`) |

This page summarises the organisation and conventions and gives real examples. Examples marked *captured* come from a local run against `seed_demo` data (2026-11-16); IDs and timestamps will differ on your machine.

## Conventions

| Topic | Convention |
|---|---|
| Base path | `/api/v1/` |
| Format | JSON request and response |
| Authentication | `Authorization: Bearer <access-token>` (see [05](05-authentication-and-permissions.md)) |
| Decimals | JSON strings (`"85.00"`, `"2.000"`) |
| Datetimes | ISO 8601, UTC (`2026-11-16T21:47:58.267188Z`) |
| Pagination | All list endpoints: `?page=N&page_size=M` (default 20, max 100). Response: `count`, `next`, `previous`, `results` |
| Search / ordering | `?search=term`, `?ordering=field` or `-field` (fields differ per endpoint, below) |
| Actions | Business actions are `POST /<resource>/{id}/<verb>/` |
| Errors | `{"error": {"code", "message", "details"}}` (see [Error responses](#error-responses)) |

## Endpoint groups

"Auth" column: **Public**, **User** (any authenticated active user), or the allowed roles. Details per role: [05](05-authentication-and-permissions.md#permission-matrix).

### Authentication and users

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/token/` | Public (5/min) | Obtain access + refresh tokens |
| POST | `/auth/token/refresh/` | Public | Rotate refresh token, get new access |
| POST | `/auth/logout/` | User | Blacklist a refresh token (body `{"refresh": "..."}`) → 204 |
| GET | `/auth/me/` | User | Current user profile |
| GET, POST | `/users/` | ADMIN | List / create users |
| GET, PUT, PATCH | `/users/{id}/` | ADMIN | Retrieve / update (no DELETE) |

### Partners (`/partners/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/partners/customers/`, `/partners/suppliers/` | User | List. Params: `is_active`, `search` (name, email, phone), `ordering` (`name`, `created_at`) |
| POST | same | customers: ADMIN, SALES · suppliers: ADMIN, PURCHASER | Create |
| GET, PUT, PATCH | `…/{id}/` | read: User · write: as above | Retrieve / update |
| DELETE | `…/{id}/` | ADMIN | Delete; 409 `resource_in_use` if referenced by orders |

### Catalog (`/catalog/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/catalog/categories/` | User | List. `search` (name), `ordering` (`name`, `created_at`) |
| POST | `/catalog/categories/` | ADMIN, STOCK_MANAGER | Create (name unique, case-insensitive) |
| GET, PATCH | `/catalog/categories/{id}/` | read: User · PATCH: ADMIN, STOCK_MANAGER | |
| DELETE | `/catalog/categories/{id}/` | ADMIN | 409 if products use it |
| GET | `/catalog/products/` | User | List. Filters: `category`, `is_active`, `category_name` (case-insensitive exact), `price_min`, `price_max`; `search` (sku, name); `ordering` (`unit_price`, `name`, `sku`, `created_at`; default `sku`) |
| POST | `/catalog/products/` | ADMIN, STOCK_MANAGER | Create |
| GET, PATCH | `/catalog/products/{id}/` | read: User · PATCH: ADMIN, STOCK_MANAGER | |
| POST | `/catalog/products/{id}/deactivate/` | ADMIN, STOCK_MANAGER | Set `is_active=false` (idempotent, returns 200 with the product) |

Products have no PUT or DELETE route.

### Inventory (`/inventory/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET, POST | `/inventory/warehouses/` | read: User · POST: ADMIN, STOCK_MANAGER | List / create |
| GET, PATCH | `/inventory/warehouses/{id}/` | read: User · PATCH: ADMIN, STOCK_MANAGER | |
| GET | `/inventory/stock-levels/` | User | Params: `product`, `warehouse`, `low_stock=true` with `threshold` (default `5.000`, returns levels whose `available <= threshold`; invalid value → 400) |
| GET | `/inventory/stock-levels/{id}/` | User | |
| GET | `/inventory/stock-movements/` | User | Params: `product`, `warehouse`, `movement_type`, `created_at__gte`; newest first |
| GET | `/inventory/stock-movements/{id}/` | User | |
| POST | `/inventory/stock-adjustments/` | ADMIN, STOCK_MANAGER | Manual adjustment → 201 with the created movement |

### Sales (`/sales/sales-orders/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/sales/sales-orders/` | User | Params: `status`, `customer`, `created_at__gte` |
| POST | `/sales/sales-orders/` | ADMIN, SALES | Create draft |
| GET | `…/{id}/` | User | |
| PUT, PATCH, DELETE | `…/{id}/` | ADMIN, SALES | Draft only |
| POST | `…/{id}/confirm/`, `…/{id}/cancel/` | ADMIN, SALES | |
| POST | `…/{id}/ship/` | ADMIN, STOCK_MANAGER | |

### Purchasing (`/purchasing/`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/purchasing/purchase-orders/`, `…/{id}/` | User | (no filter parameters implemented) |
| POST | `/purchasing/purchase-orders/` | ADMIN, PURCHASER | Create draft |
| PUT, PATCH, DELETE | `…/{id}/` | ADMIN, PURCHASER | Draft only |
| POST | `…/{id}/place/`, `…/{id}/cancel/` | ADMIN, PURCHASER | |
| POST | `…/{id}/receive/` | ADMIN, STOCK_MANAGER | 201 new receipt, 200 idempotent replay |
| GET | `/purchasing/receipts/`, `…/{id}/` | User | |

### Dashboard, audit, health

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/dashboard/summary/` | User | Aggregated statistics |
| GET | `/dashboard/audit-logs/`, `…/{id}/` | ADMIN | Params: `action`, `object_type`, `object_id`, `actor`; newest first |
| GET | `/health/` | Public | `{"status": "ok"}` |

Workflow semantics for the action endpoints are in [04](04-business-workflows.md).

## Examples

### Login

```http
POST /api/v1/auth/token/
Content-Type: application/json

{"email": "admin@example.com", "password": "<your-password>"}
```

```json
{"refresh": "<jwt>", "access": "<jwt>"}
```

### Current user (*captured*)

```json
{"id": 3, "email": "verify.admin@stockflow.local", "username": "verify.admin@stockflow.local",
 "first_name": "", "last_name": "", "role": "ADMIN", "is_active": true}
```

### Paginated product list (*captured*, `?page_size=2`)

```json
{
  "count": 20,
  "next": "http://localhost:8000/api/v1/catalog/products/?page=2&page_size=2",
  "previous": null,
  "results": [
    {"id": 16, "sku": "ELE-001", "name": "Câble électrique 10 m", "description": "",
     "category": 4, "category_name": "Électricité", "unit_price": "75.00",
     "is_active": true, "reorder_level": "0.000",
     "created_at": "2026-11-16T17:31:39.306523Z", "updated_at": "2026-11-16T17:31:39.306534Z"}
  ]
}
```

(second result omitted)

### Stock level (*captured*)

```json
{"id": 1, "product": 1, "warehouse": 1, "on_hand": "10.000",
 "reserved": "2.000", "available": "8.000", "updated_at": "2026-11-16T21:47:58.264078Z"}
```

### Create sales order, then confirm (*captured*)

Request:

```json
{"customer": 1, "warehouse": 1, "notes": "verify",
 "lines": [{"product": 1, "quantity": "2.000"}]}
```

Response `201` (note `unit_price: null` before confirmation):

```json
{"id": 1, "number": "SO-000001", "customer": 1, "customer_name": "Atlas Matériaux",
 "warehouse": 1, "warehouse_name": "Entrepôt Casablanca", "status": "DRAFT", "notes": "verify",
 "created_by": 3, "confirmed_at": null, "shipped_at": null, "cancelled_at": null,
 "lines": [{"id": 1, "product": 1, "product_name": "Marteau", "quantity": "2.000",
            "unit_price": null, "line_total": null}],
 "total": null}
```

`POST /api/v1/sales/sales-orders/1/confirm/` → `200`, `status: "CONFIRMED"`, line `unit_price: "85.00"`, `line_total: "170.000"`, `total: "170.000"`.

### Create purchase order (*captured*)

Request:

```json
{"supplier": 1, "warehouse": 1,
 "lines": [{"product": 1, "quantity_ordered": "5.000", "unit_cost": "10.00"}]}
```

The `201` response body of the create call contains only the write fields (`id`, `supplier`, `warehouse`, `lines`); retrieve the order (or call `place`) to get `number`, `status` and computed fields. See [11](11-technical-decisions.md#inconsistencies-found-during-the-documentation-audit). After `POST …/purchase-orders/1/place/`:

```json
{"id": 1, "number": "PO-27CFE6543AF0", "supplier": 1, "supplier_name": "Fournitures Atlas",
 "warehouse": 1, "warehouse_name": "Entrepôt Casablanca", "status": "ORDERED",
 "ordered_at": "2026-11-16T21:47:59.999452Z", "created_by": 3,
 "lines": [{"id": 1, "product": 1, "product_name": "Marteau", "product_sku": "OUT-001",
            "quantity_ordered": "5.000", "quantity_received": "0.000",
            "quantity_remaining": "5.000", "unit_cost": "10.00"}]}
```

### Receive goods (*captured*)

```http
POST /api/v1/purchasing/purchase-orders/1/receive/

{"idempotency_key": "3f2b8c1e-5d4a-4e7b-9a6c-1b2d3e4f5a6b",
 "lines": [{"purchase_order_line": 1, "quantity": "2.000"}]}
```

First call → `201`; identical call → `200` with the same receipt:

```json
{"id": 1, "purchase_order": 1, "purchase_order_number": "PO-27CFE6543AF0",
 "idempotency_key": "3f2b8c1e-5d4a-4e7b-9a6c-1b2d3e4f5a6b", "received_by": 3,
 "created_at": "2026-11-16T21:48:00.463377Z",
 "lines": [{"id": 1, "purchase_order_line": 1, "product_name": "Marteau",
            "product_sku": "OUT-001", "quantity": "2.000"}]}
```

### Stock adjustment (*captured*)

```http
POST /api/v1/inventory/stock-adjustments/

{"product": 1, "warehouse": 1, "quantity_delta": "-1.000", "reason": "verification"}
```

```json
{"id": 44, "product": 1, "warehouse": 1, "movement_type": "ADJUSTMENT",
 "on_hand_delta": "-1.000", "reserved_delta": "0.000", "reference": "",
 "reason": "verification", "created_by": 3, "created_at": "2026-11-16T21:48:01.283190Z"}
```

### Dashboard summary (*captured*)

```json
{"products_count": 20, "active_products_count": 20, "categories_count": 4,
 "customers_count": 3, "suppliers_count": 2, "warehouses_count": 2,
 "products_out_of_stock": 0, "products_low_stock": 0,
 "stock_value_at_list_price": "17220",
 "sales_orders_by_status": {}, "purchase_orders_by_status": {}}
```

Definitions: `products_out_of_stock` counts **active** products whose total `on_hand` is ≤ 0 (including products with no stock row); `products_low_stock` counts active products with `0 < available ≤ reorder_level` (so it stays 0 while `reorder_level` is 0); `stock_value_at_list_price` sums `on_hand × product.unit_price` over all stock levels.

### Audit log entry (*captured*)

```json
{"id": 7, "actor": 3, "actor_email": "verify.admin@stockflow.local",
 "action": "purchase_order.received", "object_type": "purchasing.PurchaseOrder", "object_id": 1,
 "payload": {"number": "PO-27CFE6543AF0", "receipt_id": 1, "status": "PARTIALLY_RECEIVED",
             "lines": [{"purchase_order_line": 1, "quantity": "2.000"}]},
 "created_at": "2026-11-16T21:48:00.475036Z"}
```

Recorded actions: `sales_order.created|updated|deleted|confirmed|shipped|cancelled` and `purchase_order.created|placed|cancelled|received`.

## Error responses

| HTTP | `code` | Typical cause | Example (*captured* unless noted) |
|---|---|---|---|
| 400 | `validation_error` | Invalid or missing fields | `{"error":{"code":"validation_error","message":"Validation failed.","details":{"sku":["This field may not be blank."],"category":["This field is required."],"unit_price":["This field is required."]}}}` |
| 401 | `not_authenticated` | No/invalid token | `{"error":{"code":"not_authenticated","message":"Request failed.","details":{"detail":"Authentication credentials were not provided."}}}` |
| 403 | DRF default (`permission_denied`) | Role not allowed | Not captured in the verification run; covered by tests |
| 404 | `request_error` | Unknown id | `{"error":{"code":"request_error","message":"Request failed.","details":{"detail":"No SalesOrder matches the given query."}}}` |
| 405 | `method_not_allowed` | Verb not routed (for example `DELETE /users/1/`) | `{"error":{"code":"method_not_allowed","message":"Request failed.","details":{"detail":"Method \"DELETE\" not allowed."}}}` |
| 409 | `invalid_transition` | State machine violation | `{"error":{"code":"invalid_transition","message":"Only DRAFT or CONFIRMED orders can be cancelled.","details":{"current_status":"SHIPPED"}}}` |
| 409 | `insufficient_stock` | Not enough available stock | `{"error":{"code":"insufficient_stock","message":"Not enough available stock.","details":{"product":2,"warehouse":1,"available":"10.000","requested_change":"9999.000"}}}` |
| 409 | `over_receipt` | Receipt exceeds remaining quantity | `…"details":{"purchase_order_line":1,"remaining":"3.000","requested":"99.000"}` |
| 409 | `idempotency_conflict` | Same key, different payload | `{"error":{"code":"idempotency_conflict","message":"This idempotency key was already used with another payload.","details":{}}}` |
| 409 | `empty_order`, `business_rule_violation` | Placing an empty purchase order; inactive customer/warehouse/product at confirmation | Not captured |
| 409 | `resource_in_use` | Deleting a referenced object | Category delete returns the **non-standard** body `{"code":"resource_in_use","detail":"This category cannot be deleted because it is used by products."}`; other resources use the standard envelope via the global handler |
| 429 | DRF throttle code | Rate limit exceeded | Not captured |
| 500 | — | Unhandled error | Generic Django 500; details only in server logs |

Rule of thumb: **400** means the request itself is invalid; **409** means the request is valid but the current state forbids it.
