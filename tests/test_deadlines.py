from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from fantasy.deadlines import next_gameweek, snapshot_missing
from fantasy.models import FantasyTeam, GameweekScore, SquadPlayer
from fantasy.tasks import update_gameweek_scores
from players.models import Fixture, Gameweek, Player, PlayerFixtureStats, Position
from players.models import Team as Club


class DeadlineTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.gw1 = Gameweek.objects.create(number=1, name='Gameweek 1', deadline=now - timedelta(days=10))
        self.gw2 = Gameweek.objects.create(number=2, name='Gameweek 2', deadline=now - timedelta(days=1))
        self.gw3 = Gameweek.objects.create(number=3, name='Gameweek 3', deadline=now + timedelta(days=5))

        self.club = Club.objects.create(fpl_id=1, name='Alpha FC', short_name='ALP')
        self.other = Club.objects.create(fpl_id=2, name='Beta FC', short_name='BET')
        forward = Position.objects.create(fpl_id=4, name='Forward', short_name='FWD')
        self.player = Player.objects.create(
            fpl_id=1, first_name='Test', last_name='Striker', web_name='Striker',
            team=self.club, position=forward, price=Decimal('8.0'),
        )

        user = get_user_model().objects.create_user('tester', password='pass12345')
        self.team = FantasyTeam.objects.create(user=user, name='Test XI')
        # Pretend the team was created 5 days ago: after GW1's deadline, before GW2's
        FantasyTeam.objects.filter(pk=self.team.pk).update(created_at=now - timedelta(days=5))
        self.team.refresh_from_db()
        self.entry = SquadPlayer.objects.create(
            fantasy_team=self.team, player=self.player, is_starter=True, is_captain=True
        )

    def test_next_gameweek_is_the_first_future_deadline(self):
        self.assertEqual(next_gameweek(), self.gw3)

    def test_only_gameweeks_closed_after_joining_are_frozen(self):
        self.assertEqual(snapshot_missing(self.team), 1)
        score = GameweekScore.objects.get(fantasy_team=self.team, gameweek=self.gw2)
        self.assertEqual(score.picks.count(), 1)
        self.assertFalse(GameweekScore.objects.filter(gameweek=self.gw1).exists())

    def test_freezing_twice_does_nothing(self):
        snapshot_missing(self.team)
        self.assertEqual(snapshot_missing(self.team), 0)
        self.assertEqual(GameweekScore.objects.filter(fantasy_team=self.team).count(), 1)

    def test_a_future_gameweek_is_never_frozen(self):
        snapshot_missing(self.team, include_before_joining=True)
        self.assertFalse(GameweekScore.objects.filter(gameweek=self.gw3).exists())

    def test_backfill_includes_gameweeks_before_joining(self):
        self.assertEqual(snapshot_missing(self.team, include_before_joining=True), 2)

    def test_scores_use_the_frozen_lineup_not_the_current_one(self):
        fixture = Fixture.objects.create(
            fpl_id=1, gameweek=self.gw2, home_team=self.club, away_team=self.other
        )
        PlayerFixtureStats.objects.create(
            player=self.player, fixture=fixture, minutes=90, goals_scored=1
        )

        snapshot_missing(self.team)

        # The manager benches the player after the deadline
        self.entry.is_starter = False
        self.entry.save()

        update_gameweek_scores(self.gw2)
        score = GameweekScore.objects.get(fantasy_team=self.team, gameweek=self.gw2)
        self.assertEqual(score.points, (2 + 4) * 2)  # appearance + goal, doubled for the captain