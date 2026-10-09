import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from players.models import Player


class Command(BaseCommand):
    help = "Run on every deploy: migrate, collect static files, create the admin, load data on first run"

    def handle(self, *args, **options):
        call_command('migrate', interactive=False)
        call_command('collectstatic', interactive=False, verbosity=0)
        self.create_admin()
        self.load_data_if_empty()

    def create_admin(self):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        if not username or not os.environ.get('DJANGO_SUPERUSER_PASSWORD'):
            return
        if get_user_model().objects.filter(username=username).exists():
            return
        try:
            call_command('createsuperuser', interactive=False)
            self.stdout.write(f'Created admin user {username}')
        except Exception as error:  # the site should still start
            self.stdout.write(self.style.WARNING(f'Could not create the admin: {error}'))

    def load_data_if_empty(self):
        if Player.objects.exists():
            return
        self.stdout.write('First run: loading football data...')
        try:
            call_command('import_data')
            call_command('import_stats')
            call_command('update_points')
        except Exception as error:  # the site should still start if the data feed is down
            self.stdout.write(self.style.WARNING(f'Could not load all the data yet: {error}'))