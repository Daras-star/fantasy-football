import random
from collections import Counter
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fantasy import rules
from fantasy.models import FantasyTeam, SquadPlayer
from players.models import Player

LINEUP = {'GKP': 1, 'DEF': 4, 'MID': 4, 'FWD': 2}  # a 4-4-2 starting XI


class Command(BaseCommand):
    help = "Create demo managers with random valid squads, for testing leaderboards"

    def add_arguments(self, parser):
        parser.add_argument("count", nargs="?", type=int, default=5, help="How many demo teams")

    def handle(self, *args, **options):
        players = list(Player.objects.select_related("team", "position"))
        if not players:
            raise CommandError("No players found. Run import_data first.")

        by_position = {}
        for player in players:
            by_position.setdefault(player.position.short_name, []).append(player)
        cheapest = min(player.price for player in players)

        User = get_user_model()
        for number in range(1, options["count"] + 1):
            username = f"demo{number}"
            if User.objects.filter(username=username).exists():
                continue

            squad = self.build_squad(by_position, cheapest)
            if squad is None:
                raise CommandError("Could not build a valid squad. Run the command again.")

            with transaction.atomic():
                user = User.objects.create_user(username, password="demo12345")
                team = FantasyTeam.objects.create(user=user, name=f"Demo FC {number}")
                self.save_squad(team, squad)
            self.stdout.write(f"Created {username} ({team.name})")

        self.stdout.write(self.style.SUCCESS("Done. Now run: python manage.py update_points --backfill"))

    def build_squad(self, by_position, cheapest):
        for _ in range(200):
            picked = []
            clubs = Counter()
            cost = Decimal("0.0")
            complete = True

            for code, needed in rules.POSITION_LIMITS.items():
                pool = list(by_position.get(code, []))
                random.shuffle(pool)
                chosen = 0
                for player in pool:
                    if chosen == needed:
                        break
                    if clubs[player.team_id] >= rules.MAX_PER_CLUB:
                        continue
                    slots_left = rules.SQUAD_SIZE - len(picked) - 1
                    # keep enough money to fill the remaining slots with the cheapest players
                    if cost + player.price + cheapest * slots_left > rules.BUDGET:
                        continue
                    picked.append(player)
                    clubs[player.team_id] += 1
                    cost += player.price
                    chosen += 1
                if chosen < needed:
                    complete = False
                    break

            if complete and not rules.validate_squad(picked):
                return picked
        return None

    def save_squad(self, team, squad):
        starters = []
        for code, count in LINEUP.items():
            group = [p for p in squad if p.position.short_name == code]
            starters += random.sample(group, count)
        starter_ids = {p.pk for p in starters}
        outfield = [p for p in starters if p.position.short_name != "GKP"]
        captain, vice = random.sample(outfield, 2)

        SquadPlayer.objects.bulk_create(
            SquadPlayer(
                fantasy_team=team,
                player=p,
                is_starter=p.pk in starter_ids,
                is_captain=p.pk == captain.pk,
                is_vice_captain=p.pk == vice.pk,
            )
            for p in squad
        )