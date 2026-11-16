
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

EXPOSE 8000

# Development environment
FROM base AS dev

COPY requirements/ requirements/

RUN pip install --no-cache-dir -r requirements/dev.txt

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Production environment
FROM base AS prod

COPY requirements/ requirements/

RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . .

# Collect static files at build time (dummy values are used only for this step)
RUN SECRET_KEY=build-only-not-a-secret \
    DATABASE_URL=sqlite:////tmp/build.db \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    python manage.py collectstatic --noinput

RUN useradd -m appuser \
    && chown -R appuser /app

USER appuser

# Applies migrations, optionally creates the first admin, then starts gunicorn.
# The port comes from $PORT (set by most platforms) and falls back to 8000.
CMD ["sh", "-c", "python manage.py migrate --noinput && (if [ -n \"$DJANGO_SUPERUSER_EMAIL\" ] && [ -n \"$DJANGO_SUPERUSER_PASSWORD\" ]; then python manage.py createsuperuser --noinput || true; fi) && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3"]
