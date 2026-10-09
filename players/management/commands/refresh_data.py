from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Download the latest results and recalculate every team's points (run hourly)"

    def handle(self, *args, **options):
        for name in ('import_data', 'import_stats', 'update_points'):
            self.stdout.write(f'Running {name}...')
            try:
                call_command(name)
            except CommandError as error:
                self.stdout.write(self.style.WARNING(f'{name}: {error}'))
        self.stdout.write(self.style.SUCCESS('Refresh finished.'))