# The client is built here, in the image, and not in the release phase.
#
# Django serves the bundle off its own filesystem — WHITENOISE_ROOT and the
# template DIRS both point at frontend/app/dist. On every managed platform the
# release command runs in a throwaway container, so a bundle built there is
# gone before the web process starts. It has to be baked in, which is what the
# first stage does.

# ---- 1. The client -----------------------------------------------------------
FROM node:24-slim AS client

WORKDIR /client

# Dependencies first: this layer is rebuilt only when the lockfile moves.
COPY frontend/app/package.json frontend/app/package-lock.json ./
RUN npm ci

COPY frontend/app/ ./
RUN npm run build


# ---- 2. The server -----------------------------------------------------------
FROM python:3.12-slim AS server

# DJANGO_SETTINGS_MODULE is set here, not left to a default. wsgi.py defaults to
# production, but manage.py defaults to *development* — so every release command
# and every one-off shell in this image would otherwise run against dev settings:
# `check --deploy` would inspect the wrong configuration, and the DEBUG guard on
# seed_demo_clinic and seed_demo_staff would read True and let them invent
# patients in the live database. Setting it once here arms both.
#
# Unbuffered so a crash loop shows its traceback in the platform's logs rather
# than dying with the buffer unflushed.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/base.txt

COPY manage.py ./
COPY backend/ backend/
COPY frontend/static/ frontend/static/
COPY --from=client /client/dist/ frontend/app/dist/

# collectstatic also has to happen at build time, and for a sharper reason: the
# staticfiles storage is CompressedManifestStaticFilesStorage, so every {% static %}
# reference is resolved through a manifest that only exists once this has run.
# Without it /admin/ raises rather than rendering unstyled.
#
# These values satisfy the production settings for the length of this command
# only. Nothing reads them at runtime, and collectstatic never opens the database.
RUN SECRET_KEY=build-time-only-not-a-secret \
    ALLOWED_HOSTS=localhost \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    python manage.py collectstatic --noinput

# Run as nobody. A container that is rooted in its own filesystem is one
# vulnerability away from being rooted in someone else's.
RUN useradd --system --create-home --uid 10001 hmis \
    && chown -R hmis:hmis /app
USER hmis

EXPOSE 8000
CMD ["sh", "-c", "gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-3} --access-logfile - --error-logfile -"]
