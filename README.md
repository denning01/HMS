# Hospital Management System

Django-based HMS for a single-site clinic: Registration, Triage, Consultation,
Laboratory, Pharmacy, Procedure/Injection Room, Billing and Appointment Booking,
sharing one patient record and one visit record.

Behaviour spec: `HMS_Documentation.md` (workflow, roles, permissions matrix).

## Layout

Backend and frontend are separated at the top level; the stack is unchanged.

```
backend/          Django: models, views, URLs, settings
  apps/           accounts, patients, triage
  config/         settings/, urls.py, wsgi.py, asgi.py
frontend/         Everything the browser receives
  templates/      accounts, patients, triage
  static/         css/, js/
manage.py         Stays at the repo root; puts backend/ on the path
```

`manage.py`, `pytest.ini` (`pythonpath = backend`) and the `Procfile`
(`gunicorn --chdir backend`) each put `backend/` on the import path, so
`config.*` and `apps.*` import unchanged.

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

`backend/config/settings/` is split three ways:

- `base.py` — shared; reads all secrets and `DATABASE_URL` from the environment
- `dev.py` — local default (`manage.py` points here)
- `prod.py` — `DEBUG=False`, HTTPS/cookie hardening, stdout logging

`manage.py` defaults to `dev`; `wsgi.py`/`asgi.py` default to `prod`, so a
deployment that forgets to set `DJANGO_SETTINGS_MODULE` fails closed rather
than serving with `DEBUG=True`. Override with
`DJANGO_SETTINGS_MODULE=config.settings.prod` for local prod checks.

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

## Price list

Billing prices everything from the `Service` catalogue; nobody types an amount
onto a bill. A starting list of 13 items is seeded with:

```bash
.venv/bin/python manage.py seed_services   # idempotent; never overwrites prices
```

It creates only what is missing, so running it on a later deploy will not reset
prices the clinic has set for itself. Prices are maintained in the admin
afterwards, and every charge copies the price it was raised at, so changing the
list never rewrites a bill already issued.

## How billing gates the departments

Each visit is either **pay per service** (the default — a department acts on a
charge once that line is paid) or **consolidated** (staff and corporate accounts
accumulate charges and settle at the end, and work is never held up). Phase 3
onwards asks `line.is_cleared` rather than reading payment state directly.

## Build status

| Phase | Module | State |
|---|---|---|
| 0 | Foundation, auth, roles | Done |
| 1 | Registration, Triage | Done |
| 2 | Billing: price list, bills, payment, collections | Done |
| 3–8 | Consultation, Lab, Pharmacy, Procedure, Appointments | Next |
| 9–10 | Reporting, UAT, go-live | Not started |

## Tests

```bash
.venv/bin/pytest
```
