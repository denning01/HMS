# Release runs before the new code serves traffic. In order: fail on a
# misconfigured deploy, build the client, migrate, and make sure the role groups
# exist — without them no account can be given access to anything.
release: python manage.py check --deploy --fail-level ERROR && npm --prefix frontend/app ci && npm --prefix frontend/app run build && python manage.py migrate --noinput && python manage.py seed_roles
web: gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:$PORT
