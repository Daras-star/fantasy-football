from decimal import Decimal

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from players.models import Fixture, Gameweek, Player, Position, Team

# The Fantasy Premier League website's public data feed (free, no login needed).
# It's unofficial and can change, so this is the only file that knows about it.
API_URL = "https://fantasy.premierleague.com/api"
HEADERS = {"User-Agent": "fantasy-football-learning-project"}


class Command(BaseCommand):
    help = "Download teams, players, gameweeks and fixtures from the Fantasy Premier League feed."

    def handle(self, *args, **options):
        self.stdout.write("Downloading data...")
        bootstrap = self.get_json("bootstrap-static/")
        fixtures = self.get_json("fixtures/")

        # One transaction: either everything is saved, or nothing is.
        with transaction.atomic():
            teams = self.import_teams(bootstrap["teams"])
            positions = self.import_positions(bootstrap["element_types"])
            gameweeks = self.import_gameweeks(bootstrap["events"])
            self.import_players(bootstrap["elements"], teams, positions)
            self.import_fixtures(fixtures, teams, gameweeks)

        self.stdout.write(self.style.SUCCESS("Done."))

    def get_json(self, path):
        url = f"{API_URL}/{path}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise CommandError(
                f"Could not download {url}: {exc}. "
                "If the game is being updated, try again in a while."
            )

    def import_teams(self, rows):
        teams = {}
        for row in rows:
            team, _ = Team.objects.update_or_create(
                fpl_id=row["id"],
                defaults={"name": row["name"], "short_name": row["short_name"]},
            )
            teams[row["id"]] = team
        self.stdout.write(f"  {len(teams)} teams")
        return teams

    def import_positions(self, rows):
        positions = {}
        for row in rows:
            position, _ = Position.objects.update_or_create(
                fpl_id=row["id"],
                defaults={
                    "name": row["singular_name"],
                    "short_name": row["singular_name_short"],
                },
            )
            positions[row["id"]] = position
        self.stdout.write(f"  {len(positions)} positions")
        return positions

    def import_gameweeks(self, rows):
        gameweeks = {}
        for row in rows:
            gameweek, _ = Gameweek.objects.update_or_create(
                number=row["id"],
                defaults={
                    "name": row["name"],
                    "deadline": parse_datetime(row["deadline_time"]),
                    "finished": row["finished"],
                    "is_current": row["is_current"],
                    "is_next": row["is_next"],
                },
            )
            gameweeks[row["id"]] = gameweek
        self.stdout.write(f"  {len(gameweeks)} gameweeks")
        return gameweeks

    def import_players(self, rows, teams, positions):
        for row in rows:
            Player.objects.update_or_create(
                fpl_id=row["id"],
                defaults={
                    "first_name": row["first_name"],
                    "last_name": row["second_name"],
                    "web_name": row["web_name"],
                    "team": teams[row["team"]],
                    "position": positions[row["element_type"]],
                    "price": Decimal(row["now_cost"]) / 10,  # the feed sends 65 for 6.5m
                    "status": row["status"],
                    "news": row["news"],
                    "total_points": row["total_points"],
                },
            )
        self.stdout.write(f"  {len(rows)} players")

    def import_fixtures(self, rows, teams, gameweeks):
        for row in rows:
            kickoff = row["kickoff_time"]
            Fixture.objects.update_or_create(
                fpl_id=row["id"],
                defaults={
                    "gameweek": gameweeks.get(row["event"]),  # None if not scheduled yet
                    "home_team": teams[row["team_h"]],
                    "away_team": teams[row["team_a"]],
                    "kickoff": parse_datetime(kickoff) if kickoff else None,
                    "home_score": row["team_h_score"],
                    "away_score": row["team_a_score"],
                    "started": bool(row["started"]),
                    "finished": bool(row["finished"]),
                },
            )
        self.stdout.write(f"  {len(rows)} fixtures")