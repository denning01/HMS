# Runbook

What to do to put this clinic's system live, keep it running, and get it back
when something goes wrong. Written for whoever is on call, not for whoever wrote
it.

## What is running

| Piece | What it is | Where it fails visibly |
|---|---|---|
| Web process | Gunicorn serving Django: `/api/`, `/admin/`, `/healthz/`, and the client's `index.html` for every other path | `/healthz/` stops returning 200 |
| Database | PostgreSQL 16. Everything is here — patients, visits, money, stock | `/healthz/` returns 503 with `"database": "unreachable"` |
| Client | A static bundle built at release time and served by WhiteNoise from the same origin | Screens load but every request 404s, or the page is blank after a deploy |

There is no queue, no cache and no background worker. A request either finishes
or it does not, which is deliberate: a clinic that cannot take payment because a
worker is stuck is worse than one that waits two seconds.

## First deploy

1. **Provision** a PostgreSQL 16 database and note its connection URL.
2. **Set the environment** on the web process:

   | Variable | Value |
   |---|---|
   | `SECRET_KEY` | 50+ random characters. `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"` |
   | `DATABASE_URL` | `postgres://user:password@host:5432/dbname` |
   | `ALLOWED_HOSTS` | The clinic's domain, comma-separated. No wildcard. |
   | `CSRF_TRUSTED_ORIGINS` | `https://the-clinic-domain` |
   | `DJANGO_SETTINGS_MODULE` | Leave unset. `wsgi.py` defaults to production, so a forgotten variable fails closed rather than serving with `DEBUG=True`. |

3. **Deploy.** The release phase runs Django's deployment checks, builds the
   client, migrates, and creates the nine role groups.
4. **Seed the catalogues** once, from a one-off shell:

   ```bash
   python manage.py seed_services      # the price list
   python manage.py seed_lab_tests     # specimen types and normal ranges
   python manage.py seed_stock_items   # the shelf, and the consumables
   ```

   All three are idempotent and none overwrites anything, so re-running them
   after the clinic has set its own prices is safe.

5. **Create the first administrator:**

   ```bash
   python manage.py createsuperuser
   ```

   Then sign in and create the real staff accounts under **Staff and roles**.
   The superuser holds every role; nobody should work day to day as one.

6. **Walk it once** before anyone relies on it — the checks under *After every
   release*, plus one real patient end to end.

Do **not** run `seed_demo_staff` or `seed_demo_clinic` against production. Both
refuse with `DEBUG` off; that refusal is the last line of defence, not the plan.

## Every release

The release phase does everything. If it fails, the old version keeps serving —
that is the point of doing it there rather than on boot.

| Step | Fails when |
|---|---|
| `check --deploy` | A setting that would be a breach is missing or wrong |
| `npm ci && npm run build` | The client does not build |
| `migrate --noinput` | A migration conflicts with the live schema |
| `seed_roles` | Never, in practice — it only creates what is missing |

### After every release

1. `/healthz/` returns `{"status": "ok", "database": "ok"}`.
2. Sign in. A blank page here usually means the built bundle did not ship — the
   shell is never cached, so it is not a stale `index.html`.
3. Open the till. It reads live money; if it renders, the API, the session
   cookie and the database are all working.
4. Take nothing and change nothing. Reading is enough to prove the path.

## Backups

Nothing in this system can be reconstructed from anywhere else. There is no
paper copy of a receipt, a result or a stock count once the clinic stops keeping
one.

```bash
pg_dump "$DATABASE_URL" --format=custom --file=hms-$(date +%F).dump
```

- **Daily**, after closing, and keep 30 days.
- **Before every release** that includes a migration.
- **Restore into a scratch database once a month.** A backup nobody has restored
  is a file, not a backup.

```bash
pg_restore --clean --if-exists --dbname="$SCRATCH_DATABASE_URL" hms-2026-01-31.dump
```

## Rolling back

**Code only, no migration in the release:** redeploy the previous build. Nothing
else is needed — the client and the server ship together.

**A release that migrated:** do not roll the code back first. Work out what the
migration did:

- *Additive* (a new table or a nullable column — which is all of this project's
  migrations so far): the previous code ignores it. Roll the code back and leave
  the schema alone.
- *Destructive* (a dropped or renamed column): roll forward with a fix, or
  restore the pre-release backup and accept losing what was entered since. There
  is no third option, which is why the backup before a migration is not
  optional.

## When something is wrong

**`/healthz/` returns 503.** The database is unreachable. The error is in the
web process logs, not in the response — the response deliberately says nothing
about the host, user or database name to an unauthenticated caller.

**A department says a paid order has not reached them.** Check the charge, not
the department. Everything a department can act on is gated on
`InvoiceLine.is_cleared`, so the question is always whether that line is paid
(pay-per-service) or the visit is consolidated. The order's own screen shows
which.

**A visit will not close.** By design: either a department still has work on it,
or money is owing. The refusal message names which. Closing would take the bill
off the till and the order off the worklist, hiding it from the only people who
could settle it.

**The shelf disagrees with what was dispensed.** It cannot, for anything the
system did — every movement writes a `StockMovement` in the same transaction
that changes the batch balance, and a test proves they reconcile. A disagreement
means stock left the shelf without being recorded, which is a conversation at
the counter, not a bug. Read the movements on the item's own screen: each one
names the person and, where there was one, the patient.

**Somebody is locked out.** An administrator resets the password under **Staff
and roles**. If every administrator is locked out, `manage.py createsuperuser`
from a one-off shell is the way back in; the system deliberately will not let an
administrator remove their own last way in through the app.

## What this system does not do

State plainly, so nobody is surprised at the wrong moment:

- **No refunds.** A paid charge cannot be cancelled in the system. It is a
  conversation at the till and a manual adjustment.
- **No insurance or NHIF.** Pay-per-service and consolidated billing only. The
  invoice structure is built so a payer type can be added without reshaping
  billing, but it is not there.
- **No SMS reminders** for appointments.
- **No cost on consultation or laboratory revenue.** Profit is overstated by
  whatever reagents and clinical time cost; only the pharmacy and the procedure
  room carry a recorded cost.
- **One site.** One patient register, one price list, one shelf.
