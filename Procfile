release: python manage.py migrate --noinput
web: gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:$PORT
