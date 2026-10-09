import sqlite3
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

KEEP = 14  # how many daily backups to keep


class Command(BaseCommand):
    help = "Make a safe copy of the SQLite database in the backups folder (one per day)"

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if not database['ENGINE'].endswith('sqlite3'):
            raise CommandError('This command only works with SQLite.')

        folder = settings.BASE_DIR / 'backups'
        folder.mkdir(exist_ok=True)
        target = folder / f"db-{date.today():%Y%m%d}.sqlite3"
        if target.exists():
            target.unlink()

        source = sqlite3.connect(database['NAME'])
        copy = sqlite3.connect(target)
        try:
            source.backup(copy)
        finally:
            copy.close()
            source.close()

        for old in sorted(folder.glob('db-*.sqlite3'))[:-KEEP]:
            old.unlink()

        self.stdout.write(self.style.SUCCESS(f'Backup saved: {target.name}'))