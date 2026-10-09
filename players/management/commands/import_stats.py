import time

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from players.models import Fixture, Gameweek, Player, PlayerFixtureStats

BASE_URL = "https://fantasy.premierleague.com/api/"
HEADERS = {"User-Agent": "Mozilla/5.0 (learning project)"}

# name used by the feed -> field on PlayerFixtureStats
STAT_FIELDS = {
    "minutes": "minutes",
    "goals_scored": "goals_scored",
    "assists": "assists",
    "clean_sheets": "clean_sheets",
    "goals_conceded": "goals_conceded",
    "own_goals": "own_goals",
    "penalties_saved": "penalties_saved",
    "penalties_missed": "penalties_missed",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
    "saves": "saves",
    "bonus": "bonus",
    "defensive_contribution": "defensive_contribution",
}


def fetch(path):
    response = requests.get(BASE_URL + path, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


class Command(BaseCommand):
    help = "Import match-by-match player stats for gameweeks that have started"

    def add_arguments(self, parser):
        parser.add_argument(
            "gameweeks",
            nargs="*",
            type=int,
            help="Gameweek numbers to import (default: every gameweek that has started)",
        )

    def handle(self, *args, **options):
        numbers = options["gameweeks"]

        if numbers:
            gameweeks = list(Gameweek.objects.filter(number__in=numbers).order_by("number"))
            unknown = set(numbers) - {g.number for g in gameweeks}
            if unknown:
                raise CommandError(
                    f"Unknown gameweek(s): {sorted(unknown)}. Run import_data first."
                )
        else:
            gameweeks = list(
                Gameweek.objects.filter(Q(finished=True) | Q(is_current=True)).order_by("number")
            )

        if not gameweeks:
            raise CommandError("No started gameweeks found. Run import_data first.")

        players = {p.fpl_id: p for p in Player.objects.all()}
        fixtures = {f.fpl_id: f for f in Fixture.objects.all()}

        for index, gameweek in enumerate(gameweeks):
            if index:
                time.sleep(0.5)  # be polite to the server
            self.import_gameweek(gameweek, players, fixtures)

        total = PlayerFixtureStats.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Done. {total} stat rows in the database."))

    def import_gameweek(self, gameweek, players, fixtures):
        try:
            data = fetch(f"event/{gameweek.number}/live/")
        except (requests.RequestException, ValueError) as error:
            raise CommandError(f"Could not download gameweek {gameweek.number}: {error}")

        created = updated = skipped = 0

        with transaction.atomic():
            for element in data.get("elements", []):
                player = players.get(element.get("id"))
                if player is None:
                    skipped += 1
                    continue

                for block in element.get("explain", []):
                    fixture = fixtures.get(block.get("fixture"))
                    if fixture is None:
                        skipped += 1
                        continue

                    values = {field: 0 for field in STAT_FIELDS.values()}
                    for stat in block.get("stats", []):
                        field = STAT_FIELDS.get(stat.get("identifier"))
                        if field:
                            values[field] = max(0, int(stat.get("value", 0)))

                    if values["minutes"] <= 0:
                        continue  # didn't play in this match

                    _, was_created = PlayerFixtureStats.objects.update_or_create(
                        player=player, fixture=fixture, defaults=values
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        message = f"{gameweek.name}: {created} new, {updated} updated"
        if skipped:
            message += f", {skipped} skipped (unknown player or fixture, run import_data first)"
        self.stdout.write(message)