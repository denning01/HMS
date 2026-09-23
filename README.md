# Hospital Management System

Django-based HMS for a single-site clinic: Registration, Triage, Consultation,
Laboratory, Pharmacy, Procedure/Injection Room, Billing and Appointment Booking,
sharing one patient record and one visit record.

Behaviour spec: `HMS_Documentation.md` (workflow, roles, permissions matrix).

## Layout

Backend and frontend are separated at the top level; the stack is unchanged.

```
backend/          Django. Serves JSON under /api/ and nothing else.
  apps/           accounts, patients, triage, billing,
                  orders, consultation, laboratory, pharmacy,
                  procedures, appointments, reporting
    */models.py     the records
    */services.py   the operations — every rule that refuses something
    */selectors.py  the reads more than one caller needs
    */serializers.py + api.py   the JSON surface
  config/         settings/, urls.py, api_urls.py, wsgi.py, asgi.py
frontend/app/     React client
  src/api/        one fetch wrapper, one file of query hooks
  src/auth/       session context and the role map
  src/components/ Layout and the shared UI vocabulary
  src/pages/      one file per screen
manage.py         Stays at the repo root; puts backend/ on the path
```

`manage.py`, `pytest.ini` (`pythonpath = backend`) and the `Procfile`
(`gunicorn --chdir backend`) each put `backend/` on the import path, so
`config.*` and `apps.*` import unchanged.

### How the two halves meet

Django serves `/api/`, `/admin/` and `/healthz/`. Every other path returns the
client's `index.html`, so a reload or a pasted link on `/billing/invoices/3`
lands in the app rather than a 404.

The client is same-origin in both environments — Vite proxies `/api` to Django
in development, WhiteNoise serves the built bundle beside it in production. So
authentication is a plain Django **session cookie**: httpOnly, never readable by
JavaScript, never stored anywhere an XSS could reach. There is no token and no
CORS configuration. Unsafe requests carry the CSRF token Django sets, which the
client fetches once from `/api/auth/csrf/` on boot.

Role gating exists on both sides and means different things. `HasAnyRole` on the
API is the security boundary. The role checks in the client are navigation: they
keep a nurse from clicking into a screen that would only refuse them.

The API answers **401** when nobody is signed in and **403** when someone is and
the answer is still no. DRF gives 403 for both under session authentication, and
the client cannot tell them apart that way — one means the session has run out
and the person should sign in again, the other means they may not do this. A 401
on any request sends the client back to the sign-in screen, wherever it was.

## Stack

- **Backend** — Django 6.1 + Django REST Framework, PostgreSQL 16
- **Client** — React 19 + Vite, React Router, TanStack Query, Tailwind CSS 4
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

# 3. Client dependencies
npm --prefix frontend/app install

# 4. Environment file
cp .env.example .env   # then fill in SECRET_KEY and DATABASE_URL

# 5. Run both halves, in two terminals
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver        # API on :8000
npm --prefix frontend/app run dev           # client on :5173
```

Develop against **http://127.0.0.1:5173/** — Vite serves the client with hot
reload and proxies `/api` to Django. `/healthz/` on :8000 reports app and
database status.

To check the production arrangement locally, build the client and let Django
serve it on :8000 alone:

```bash
npm --prefix frontend/app run build
.venv/bin/python manage.py runserver
```

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

The Administrator manages accounts and roles under **Staff and roles**: create an
account, hold several roles on it at once, set a password Django's own validators
accept, and withdraw access without deleting anyone — their name is on receipts.
An administrator cannot remove their own last way in.

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
prices the clinic has set for itself. After that the Administrator maintains the
list in the app itself, under **Price list**: add a service, change a price,
retire one. Every charge copies the price it was raised at, so changing the list
never rewrites a bill already issued, and a service code is set once and never
changed because the reports and the seeders match on it.

There is no delete anywhere in administration. A service on an issued bill and a
stock item with movements against it are both part of the record; retiring is
the way out, and every old receipt still reads correctly.

## Orders: how the departments hear from the doctor

Everything the doctor asks another department to do is one `Order` and one
charge on the visit's bill, created together. Laboratory, Pharmacy and the
Procedure room all ask the same question before acting — has billing cleared
this? — so they share one record and get one answer rather than three.

Each department attaches its own record to the order as the module is built.
The laboratory's is `LabResult`: the specimen, the findings, and the three
stamps the specification asks for — collected, recorded, released. A result is
invisible to the doctor until it is released, because until then nobody has put
their name to it. Those same stamps answer how long the bench takes: **Lab
turnaround** reports ordered-to-released over a period, split into the three
legs it is made of — waiting for a specimen, on the bench, and written but not
yet signed off — because they fail for different reasons. Tests still
outstanding are listed beside it, including the ones held at the till, since the
patient is waiting either way.

The pharmacy's is `Prescription` — the directions the drug goes out with — and
dispensing moves stock off the shelf in the same transaction, so pharmacy sales
and inventory cannot drift apart. The procedure room's is `ProcedureRecord`,
and the consumables it used are not a list on that record: they are the stock
movements that came off the shelf for it, which is the same ledger the pharmacy
keeps.

```bash
.venv/bin/python manage.py seed_lab_tests     # specimen types and normal ranges
.venv/bin/python manage.py seed_stock_items   # the shelf, and the consumables
```

Both are idempotent and neither overwrites: a reference range or a reorder level
the clinic has corrected in the admin survives the next deploy. Neither puts any
stock on the shelf — quantities arrive as batches when the pharmacist receives a
delivery, because that is where cost and expiry come from.

## Revenue and profit

Revenue is read from the payments and the lines they settled. Cost is read from
the stock that actually left the shelf, at what those units were bought for.
Both already exist as records someone signed for, so the report cannot say
anything the receipts and the ledger do not.

Two limits are stated on the screen rather than left to be discovered:

- Only the pharmacy and the procedure room have a recorded cost, so profit is
  overstated by whatever reagents and time cost in the lab and the consulting
  room.
- Revenue is recognised when the money is taken and cost when the stock moves.
  Over a week that comes out; on the boundary of a single day it can be a little
  out, and that is the honest limit of a daily profit figure drawn from two
  different events.

Wastage, expiry and stock corrections are reported as losses, never folded into
cost of sale — a bad month should not read as an expensive one.

## Stock

Cost sits on the batch, not on the drug: it is what was actually paid for those
units. Every unit in and every unit out is a `StockMovement` with a reason and a
person, written in the same transaction that changes the batch balance, and
dispensing takes the batch that expires first. Profit per day (Phase 9) is
revenue minus the cost of the units that actually left the shelf, and that
answer only exists because each movement carries the cost of the batch it came
out of.

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
| — | JSON API + React client (replaced the server-rendered screens) | Done |
| 3 | Consultation: the note, orders, closing the visit | Done |
| 4 | Laboratory: worklist, specimen, result, release | Done |
| 5 | Pharmacy: prescriptions, dispensing, stock and batches | Done |
| 6 | Procedure room: worklist, procedure done, consumables used | Done |
| 7 | Appointments: the diary, arrivals and follow-ups | Done |
| 8 | Reporting: revenue, cost and profit over a period | Done |
| 9 | Administration: price list, stock list, staff and roles | Done |
| 10 | UAT: the journey end to end, patient history, demo clinic | Done |
| — | Go-live: release phase, runbook, session hardening | Done |

Every module in the specification is built. What is deliberately not built is
listed at the end of `docs/RUNBOOK.md` — no refunds, no insurance, no SMS, no
cost recorded against consultation or laboratory revenue, one site.
| 9–10 | Reporting, UAT, go-live | Not started |

## Going live

`docs/RUNBOOK.md` is the operational document: first deploy, what the release
phase does, what to check after it, backups and restores, how to roll back a
release that migrated, and what to do when a department says a paid order has
not reached them.

The release phase runs Django's deployment checks first, so a missing
`SECRET_KEY` or a wildcard `ALLOWED_HOSTS` stops the deploy rather than serving
it. `wsgi.py` defaults to the production settings, so a deployment that forgets
`DJANGO_SETTINGS_MODULE` fails closed instead of serving with `DEBUG=True`.

Sessions follow a shift rather than a browser: refreshed on every request and
dead eight hours after the last one, so a shared screen left on overnight is
signed out by morning.

## Walking the system

For user acceptance testing, fill a development database with a clinic that has
been trading — a register of patients, stock on the shelf, and one patient at
each stage of the journey, so every queue and every report has something in it:

```bash
.venv/bin/python manage.py seed_demo_clinic   # development only; refuses with DEBUG off
```

Running it twice gives the same clinic back rather than a second attendance for
everybody. It calls the other seeders itself, and creates the demo staff account
for every role (password `demo-password-123`).

## Tests

```bash
.venv/bin/pytest                    # backend, including the whole API surface
npx --prefix frontend/app oxlint src
```

The API tests are the guard on every rule the screens used to enforce: who may
call what, what the server refuses, and that a client cannot dictate an amount.

`backend/apps/test_journey.py` is the other kind. Every other test file asks one
module whether it enforces its own rules; that one walks a single patient from
the front desk to the owner's report and asks whether the modules hand off to
each other. When it fails, the line it fails on is the step of the patient
journey that broke.
