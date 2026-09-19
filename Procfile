release: npm --prefix frontend/app ci && npm --prefix frontend/app run build && python manage.py migrate --noinput
web: gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:$PORT
