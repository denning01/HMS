# Hospital Management System

Django-based HMS for a single-site clinic: Registration, Triage, Consultation,
Laboratory, Pharmacy, Procedure/Injection Room, Billing and Appointment Booking,
sharing one patient record and one visit record.

Behaviour spec: `HMS_Documentation.md` (workflow, roles, permissions matrix).

## Stack

- Django 6.1 + server-rendered templates (HTMX + Alpine.js + Bootstrap 5)
- PostgreSQL 16
- Gunicorn + WhiteNoise for deployment

## Local setup

Prerequisites: Python 3.12, Docker.

```bash
# 1. Database (runs on 5433 so it doesn't clash with a system Postgres on 5432)
docker start hmis-postgres  # or, first time:
# docker run -d --name hmis-postgres --restart unless-stopped \
#   -e POSTGRES_USER=hmis -e POSTGRES_PASSWORD=hmis_dev_pw -e POSTGRES_DB=hmis \
#   -p 127.0.0.1:5433:5432 -v hmis_pgdata:/var/lib/postgresql/data postgres:16

# 2. Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements/dev.txt

# 3. Environment file
cp .env.example .env   # then fill in SECRET_KEY and DATABASE_URL

# 4. Run
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Then open http://127.0.0.1:8000/ — `/healthz/` reports app and database status.

## Settings

`config/settings/` is split three ways:

- `base.py` — shared; reads all secrets and `DATABASE_URL` from the environment
- `dev.py` — local default (`manage.py` points here)
- `prod.py` — `DEBUG=False`, HTTPS/cookie hardening, stdout logging

Run production settings with `DJANGO_SETTINGS_MODULE=config.settings.prod`.

## Roles

The nine roles from the specification are Django Groups, seeded with:

```bash
.venv/bin/python manage.py seed_roles     # idempotent; safe on every deploy
```

One account can hold several roles, as the specification requires. For local
walkthroughs, `seed_demo_staff` creates one account per role (development only):

```bash
.venv/bin/python manage.py seed_demo_staff
```

## Build status

| Phase | Module | State |
|---|---|---|
| 0 | Foundation, auth, roles | Done |
| 1 | Registration, Triage | Done |
| 2 | Billing engine | Next |
| 3–8 | Consultation, Lab, Pharmacy, Procedure, Appointments | Not started |
| 9–10 | Reporting, UAT, go-live | Not started |

## Tests

```bash
.venv/bin/pytest
```
