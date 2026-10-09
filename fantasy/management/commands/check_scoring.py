from django.core.management.base import BaseCommand

from fantasy.scoring import calculate_player_points
from players.models import Player


class Command(BaseCommand):
    help = "Compare our scoring with the official season totals from the feed"

    def handle(self, *args, **options):
        checked = matched = 0
        mismatches = []

        players = Player.objects.select_related("position").prefetch_related("match_stats")
        for player in players:
            rows = list(player.match_stats.all())
            if not rows and player.total_points == 0:
                continue
            code = player.position.short_name
            ours = sum(calculate_player_points(code, row) for row in rows)
            checked += 1
            if ours == player.total_points:
                matched += 1
            else:
                mismatches.append((player, ours))

        self.stdout.write(f"Checked {checked} players: {matched} match the official total.")

        if mismatches:
            mismatches.sort(key=lambda item: -abs(item[1] - item[0].total_points))
            self.stdout.write("")
            self.stdout.write("Biggest differences (ours vs official):")
            for player, ours in mismatches[:15]:
                self.stdout.write(
                    f"  {player.web_name} ({player.position.short_name}): "
                    f"{ours} vs {player.total_points}"
                )
            self.stdout.write(
                self.style.WARNING(
                    "Run import_data and import_stats back to back, then check again. "
                    "If differences remain, send me this list."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Our scoring matches the official points for every player."))