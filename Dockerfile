
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

RUN useradd -m appuser \
    && chown -R appuser /app

USER appuser

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
