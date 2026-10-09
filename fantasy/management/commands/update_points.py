from django.core.management.base import BaseCommand, CommandError

from fantasy.deadlines import snapshot_missing
from fantasy.models import FantasyTeam
from fantasy.tasks import refresh_totals, update_gameweek_scores
from players.models import Gameweek


class Command(BaseCommand):
    help = "Freeze lineups at their deadlines, then calculate every team's gameweek points"

    def add_arguments(self, parser):
        parser.add_argument(
            "gameweeks",
            nargs="*",
            type=int,
            help="Gameweek numbers to score (default: every gameweek with imported stats)",
        )
        parser.add_argument(
            "--backfill",
            action="store_true",
            help="Testing only: freeze each team's CURRENT lineup for every closed gameweek, "
                 "even ones that closed before the team was created",
        )

    def handle(self, *args, **options):
        frozen = 0
        for team in FantasyTeam.objects.all():
            frozen += snapshot_missing(team, include_before_joining=options["backfill"])
        if frozen:
            self.stdout.write(f"Froze {frozen} lineup(s) at their deadlines.")

        numbers = options["gameweeks"]
        if numbers:
            gameweeks = list(Gameweek.objects.filter(number__in=numbers).order_by("number"))
            unknown = set(numbers) - {g.number for g in gameweeks}
            if unknown:
                raise CommandError(f"Unknown gameweek(s): {sorted(unknown)}.")
        else:
            gameweeks = list(
                Gameweek.objects.filter(fixtures__player_stats__isnull=False)
                .distinct()
                .order_by("number")
            )

        if not gameweeks:
            raise CommandError("No match stats found. Run import_stats first.")

        for gameweek in gameweeks:
            scored = update_gameweek_scores(gameweek)
            self.stdout.write(f"{gameweek.name}: scored {scored} team(s)")

        refresh_totals()

        self.stdout.write("")
        self.stdout.write("Standings:")
        for team in FantasyTeam.objects.all()[:10]:
            self.stdout.write(f"  {team.name}: {team.total_points}")
        self.stdout.write(self.style.SUCCESS("Points updated."))