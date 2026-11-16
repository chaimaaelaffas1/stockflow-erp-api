#!/usr/bin/env bash
OUT=verification-report.txt
: > "$OUT"
BODY=$(mktemp)
BASE=http://localhost:8000

section(){ printf '\n\n===== %s =====\n' "$1" >> "$OUT"; echo ">> $1"; }
run(){ echo "\$ $*" >> "$OUT"; "$@" >> "$OUT" 2>&1; echo "[exit code: $?]" >> "$OUT"; }
dc(){ docker compose run --rm -T api "$@"; }

section "0. Environment"
[ -f .env ] || cp .env.example .env
run docker --version
run docker compose version
run git log --oneline -5
run docker compose build api

section "1. Versions"
run dc python --version
run dc sh -c 'pip list 2>/dev/null | grep -Ei "^(django|djangorestframework|djangorestframework-simplejwt|django-filter|drf-spectacular|psycopg|pytest|pytest-django|pytest-cov|factory-boy|ruff|gunicorn|whitenoise) "'

section "2. Ruff"
run dc ruff check .
run dc ruff format --check .

section "3. Django checks and migrations"
run dc python manage.py check
run dc python manage.py makemigrations --check --dry-run

section "4. Tests and coverage (PostgreSQL)"
run dc pytest --collect-only -q -p no:cacheprovider
run dc pytest -q -ra --cov=apps --cov-report=term -p no:cacheprovider

section "5. OpenAPI validation and sync with schema.yml"
run dc python manage.py spectacular --validate --file /tmp/s.yml
run dc sh -c 'python manage.py spectacular --file /tmp/s.yml >/dev/null 2>&1; diff -q /tmp/s.yml schema.yml && echo SCHEMA_IN_SYNC || { echo SCHEMA_DIFFERS; diff /tmp/s.yml schema.yml | head -40; }'

section "6. Live API: start, migrate, seed, admin"
run docker compose up -d --build api
for i in $(seq 1 30); do curl -sf "$BASE/api/v1/health/" >/dev/null && break; sleep 2; done
run docker compose exec -T api python manage.py migrate --noinput
run docker compose exec -T api python manage.py seed_demo
run docker compose exec -T -e DJANGO_SUPERUSER_PASSWORD='Verify-Only-Pass-2026!' api \
  python manage.py createsuperuser --noinput --email verify.admin@stockflow.local

TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/token/" -H 'Content-Type: application/json' \
  -d '{"email":"verify.admin@stockflow.local","password":"Verify-Only-Pass-2026!"}' \
  | sed -E 's/.*"access":"([^"]+)".*/\1/')

api(){ # usage: api METHOD PATH [json-body]
  local m=$1 p=$2 d=${3:-}
  if [ -n "$d" ]; then
    code=$(curl -s -o "$BODY" -w '%{http_code}' -X "$m" "$BASE$p" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$d")
  else
    code=$(curl -s -o "$BODY" -w '%{http_code}' -X "$m" "$BASE$p" -H "Authorization: Bearer $TOKEN")
  fi
  { echo "--- $m $p -> $code"; head -c 700 "$BODY"; echo; } >> "$OUT"
}
anon(){ code=$(curl -s -o "$BODY" -w '%{http_code}' "$BASE$1"); { echo "--- (anonymous) GET $1 -> $code"; head -c 300 "$BODY"; echo; } >> "$OUT"; }
newid(){ grep -o '"id":[0-9]*' "$BODY" | head -1 | cut -d: -f2; }

section "7. Read endpoints and error formats"
anon /api/v1/health/
anon /api/v1/catalog/products/
anon /api/schema/swagger-ui/
anon /api/schema/redoc/
api GET /api/v1/auth/me/
api GET /api/v1/dashboard/summary/
api GET "/api/v1/catalog/products/?page_size=2"
api GET "/api/v1/catalog/products/?search=marteau"
api GET "/api/v1/inventory/stock-levels/?page_size=2"
api GET "/api/v1/inventory/stock-levels/?low_stock=true&threshold=5"
api GET "/api/v1/inventory/stock-movements/?page_size=2"
api GET /api/v1/users/
api DELETE /api/v1/users/1/
api POST /api/v1/catalog/products/ '{"sku":"","name":"x"}'
api GET /api/v1/sales/sales-orders/999999/
api DELETE /api/v1/catalog/categories/1/

section "8. Sales flow: create, confirm, ship, invalid cancel, oversell"
api POST /api/v1/sales/sales-orders/ '{"customer":1,"warehouse":1,"notes":"verify","lines":[{"product":1,"quantity":"2.000"}]}'
SO=$(newid)
api POST /api/v1/sales/sales-orders/$SO/confirm/
api GET "/api/v1/inventory/stock-levels/?product=1&warehouse=1"
api POST /api/v1/sales/sales-orders/$SO/ship/
api GET "/api/v1/inventory/stock-levels/?product=1&warehouse=1"
api POST /api/v1/sales/sales-orders/$SO/cancel/
api POST /api/v1/sales/sales-orders/ '{"customer":1,"warehouse":1,"lines":[{"product":2,"quantity":"9999.000"}]}'
SO2=$(newid)
api POST /api/v1/sales/sales-orders/$SO2/confirm/

section "9. Purchasing flow: create, place, receive, replay, over-receipt"
api POST /api/v1/purchasing/purchase-orders/ '{"supplier":1,"warehouse":1,"lines":[{"product":1,"quantity_ordered":"5.000","unit_cost":"10.00"}]}'
PO=$(newid)
api POST /api/v1/purchasing/purchase-orders/$PO/place/
api GET /api/v1/purchasing/purchase-orders/$PO/
LINE=$(grep -o '"lines":\[{"id":[0-9]*' "$BODY" | grep -o '[0-9]*$')
KEY=3f2b8c1e-5d4a-4e7b-9a6c-1b2d3e4f5a6b
api POST /api/v1/purchasing/purchase-orders/$PO/receive/ "{\"idempotency_key\":\"$KEY\",\"lines\":[{\"purchase_order_line\":$LINE,\"quantity\":\"2.000\"}]}"
api POST /api/v1/purchasing/purchase-orders/$PO/receive/ "{\"idempotency_key\":\"$KEY\",\"lines\":[{\"purchase_order_line\":$LINE,\"quantity\":\"2.000\"}]}"
api POST /api/v1/purchasing/purchase-orders/$PO/receive/ "{\"idempotency_key\":\"$KEY\",\"lines\":[{\"purchase_order_line\":$LINE,\"quantity\":\"3.000\"}]}"
api POST /api/v1/purchasing/purchase-orders/$PO/receive/ "{\"idempotency_key\":\"7a1c2d3e-0000-4000-8000-000000000001\",\"lines\":[{\"purchase_order_line\":$LINE,\"quantity\":\"99.000\"}]}"

section "10. Stock adjustment and audit logs"
api POST /api/v1/inventory/stock-adjustments/ '{"product":1,"warehouse":1,"quantity_delta":"-1.000","reason":"verification"}'
api POST /api/v1/inventory/stock-adjustments/ '{"product":1,"warehouse":1,"quantity_delta":"0","reason":"x"}'
api GET "/api/v1/dashboard/audit-logs/?page_size=20"

echo "Done. Send me: $OUT"
