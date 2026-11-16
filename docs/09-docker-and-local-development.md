# 09 — Docker and local development

[← 08 Testing and quality](08-testing-and-quality.md) · [README](../README.md) · Next: [10 Development guide](10-development-guide.md)

## Prerequisites

| Option | Needs |
|---|---|
| Docker (recommended) | Docker Engine and Docker Compose v2 |
| Local virtualenv | Python 3.12, a reachable PostgreSQL (16 recommended), `pip` |

## Environment variables

Copy the template and edit it. `.env` is git-ignored and excluded from the image build context.

```bash
cp .env.example .env
```

| Variable | Used by | Required | Default | Notes |
|---|---|---|---|---|
| `SECRET_KEY` | Django | yes | — | Generate a new random value; never reuse the placeholder |
| `DEBUG` | Django | no | `False` | `True` only for local development |
| `ALLOWED_HOSTS` | Django | no | `[]` | Comma-separated; mandatory for any non-local host when `DEBUG` is off |
| `DATABASE_URL` | Django | yes | — | `postgresql://user:password@host:5432/dbname` |
| `LOG_LEVEL` | logging | no | `INFO` | Root logger level, console handler |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose `db` service | yes for Compose | — | Also used to build `DATABASE_URL` for the `api` container |

Production-only variables are listed [below](#production-image).

In Docker Compose the `api` service reads `.env` and then **overrides** `DATABASE_URL` to point to the `db` service, so the `localhost` URL in `.env.example` only matters for non-Docker runs.

## Docker setup (development)

`docker-compose.yml` defines two services and one volume:

| Service | Image / build | Details |
|---|---|---|
| `db` | `postgres:16` | Volume `pgdata`, health check with `pg_isready`. **No port is published** to the host |
| `api` | built from `Dockerfile`, target `dev` | `runserver 0.0.0.0:8000`, port `8000:8000`, waits for a healthy `db`, health check on `/api/v1/health/` |

The `api` image copies the source at build time and there is no bind mount, so **rebuild after code changes**.

```bash
docker compose up -d --build      # build and start
docker compose ps                 # check status / health
docker compose logs -f api
docker compose down               # stop (keeps the database volume)
docker compose down -v            # stop and DELETE the database volume
```

### Database initialisation and migrations

The database container creates the empty database from the `POSTGRES_*` variables. The dev API container does **not** run migrations automatically:

```bash
docker compose exec api python manage.py migrate
```

### Create an administrative user

```bash
docker compose exec api python manage.py createsuperuser
```

It prompts for an email and a password (login is by email). The command always creates a user with role `ADMIN`. Non-interactive form (useful in scripts):

```bash
docker compose exec -e DJANGO_SUPERUSER_PASSWORD='<choose-a-password>' api \
  python manage.py createsuperuser --noinput --email admin@example.com
```

### Optional demo data

```bash
docker compose exec api python manage.py seed_demo
```

Creates 4 categories, 20 products, 2 warehouses (`CASA-01`, `MRK-01`), 3 customers, 2 suppliers and initial stock (10 units in the first warehouse, 5 in the second, with matching `RECEIPT` movements). It also creates a technical user `demo.admin@stockflow.local` with an unusable password (it cannot log in). Safe to re-run.

### Run the application

`http://localhost:8000/` — see the [README](../README.md#api-documentation) for the Swagger/ReDoc URLs and [06](06-api-reference.md) for the endpoints. Quick check: `curl http://localhost:8000/api/v1/health/`.

### Run checks inside the container

```bash
docker compose run --rm api pytest -q
docker compose run --rm api ruff check .
docker compose run --rm api python manage.py makemigrations --check --dry-run
```

## Local setup without Docker

You need a PostgreSQL instance and a matching `DATABASE_URL` (for example a local install, or the Compose `db` service with a `ports: ["5432:5432"]` mapping added by you, since it is not published by default).

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt
cp .env.example .env                 # edit SECRET_KEY, DEBUG, DATABASE_URL
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

`manage.py` defaults to `config.settings.dev`.

## Production image

The `prod` stage of the `Dockerfile` (`docker build --target prod .`) installs `requirements/prod.txt` (adds gunicorn and WhiteNoise), runs `collectstatic` at build time with throw-away build-only values, switches to a non-root user and starts:

```text
python manage.py migrate --noinput
[createsuperuser --noinput   only if DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD are set]
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3
```

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | **Must be set to `config.settings.prod` at runtime.** The Dockerfile only sets it inline for `collectstatic`; `manage.py` and `wsgi.py` otherwise default to `config.settings.dev` (`DEBUG = True`, no HTTPS hardening) |
| `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS` | As above; required |
| `PORT` | Listening port (defaults to 8000) |
| `SECURE_SSL_REDIRECT` | Default `True`; the health endpoint is exempt |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins (admin site) |
| `SECURE_HSTS_SECONDS` | Default `0` (HSTS off) |
| `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | Optional first-admin creation on start; remove after the first boot |

The production image has not been exercised in the verification run described in [08](08-testing-and-quality.md); no deployment target is documented in the repository. Treat the production configuration as "production-like" and review it before any real deployment (see [11](11-technical-decisions.md#known-limitations)).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `django.core.exceptions.ImproperlyConfigured: Set the SECRET_KEY environment variable` | `.env` missing or without `SECRET_KEY` (also `DATABASE_URL`) |
| Code changes are not visible in Docker | The image has no bind mount; run `docker compose up -d --build` |
| Image build fails with pip `ReadTimeoutError` / name-resolution errors | Temporary network problem while downloading packages; retry the build |
| `could not translate host name "db"` when running outside Docker | The `db` host only exists inside the Compose network; use a local `DATABASE_URL` |
| `connection refused` on `localhost:5432` | The Compose `db` port is not published; install PostgreSQL locally or add a port mapping |
| `relation ... does not exist` | Migrations not applied: `docker compose exec api python manage.py migrate` |
| `DisallowedHost` | Add the host to `ALLOWED_HOSTS` |
| Port 8000 already in use | Stop the other process or change the host side of `ports` in `docker-compose.yml` |
| Tests fail with permission denied to create database | The database user needs `CREATEDB`; the default Compose user is a superuser |
| Swagger UI is blank offline | It loads assets from the jsDelivr CDN; ReDoc (`/api/schema/redoc/`) works offline |
| Windows Git Bash rewrites `/tmp/...` in container commands | Prefix the command with `MSYS_NO_PATHCONV=1` |
