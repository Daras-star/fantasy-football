web: python manage.py prepare_site && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 --log-file -
