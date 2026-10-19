from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from django.utils import timezone

from fantasy.live import live_gameweek, points_by_player
from players.models import Fixture, Gameweek, Player, PlayerFixtureStats, Position
from players.models import Team as Club


class LivePointsTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.gw1 = Gameweek.objects.create(
            number=1, name='Gameweek 1', deadline=now - timedelta(days=14), finished=True
        )
        self.gw2 = Gameweek.objects.create(
            number=2, name='Gameweek 2', deadline=now - timedelta(days=1), is_current=True
        )
        home = Club.objects.create(fpl_id=1, name='Home FC', short_name='HOM')
        away = Club.objects.create(fpl_id=2, name='Away FC', short_name='AWY')
        fwd = Position.objects.create(fpl_id=4, name='Forward', short_name='FWD')
        self.player = Player.objects.create(
            fpl_id=1, first_name='A', last_name='Striker', web_name='Striker',
            team=home, position=fwd, price=Decimal('8.0'),
        )
        self.benched = Player.objects.create(
            fpl_id=2, first_name='B', last_name='Unused', web_name='Unused',
            team=away, position=fwd, price=Decimal('4.5'),
        )
        self.fixture1 = Fixture.objects.create(
            fpl_id=1, gameweek=self.gw1, home_team=home, away_team=away
        )
        self.fixture2 = Fixture.objects.create(
            fpl_id=2, gameweek=self.gw2, home_team=home, away_team=away
        )

    def entries(self):
        return [
            SimpleNamespace(player_id=p.id, player=p) for p in (self.player, self.benched)
        ]

    def test_no_stats_means_nothing_to_show(self):
        self.assertIsNone(live_gameweek())

    def test_falls_back_to_latest_gameweek_with_stats(self):
        PlayerFixtureStats.objects.create(player=self.player, fixture=self.fixture1, minutes=90)
        self.assertEqual(live_gameweek(), self.gw1)

    def test_current_gameweek_is_used_once_it_has_stats(self):
        PlayerFixtureStats.objects.create(player=self.player, fixture=self.fixture1, minutes=90)
        PlayerFixtureStats.objects.create(player=self.player, fixture=self.fixture2, minutes=30)
        self.assertEqual(live_gameweek(), self.gw2)

    def test_points_only_for_players_who_have_played(self):
        PlayerFixtureStats.objects.create(
            player=self.player, fixture=self.fixture2, minutes=90, goals_scored=1
        )
        points = points_by_player(self.gw2, self.entries())
        # 2 for playing 60+ minutes, 4 for a forward's goal
        self.assertEqual(points, {self.player.id: 6})
        self.assertNotIn(self.benched.id, points)

    def test_other_gameweeks_are_ignored(self):
        PlayerFixtureStats.objects.create(
            player=self.player, fixture=self.fixture1, minutes=90, goals_scored=3
        )
        self.assertEqual(points_by_player(self.gw2, self.entries()), {})

    def test_lists_every_gameweek_that_has_stats(self):
        from fantasy.live import gameweeks_with_stats
        PlayerFixtureStats.objects.create(player=self.player, fixture=self.fixture1, minutes=90)
        PlayerFixtureStats.objects.create(player=self.player, fixture=self.fixture2, minutes=90)
        self.assertEqual(list(gameweeks_with_stats()), [self.gw1, self.gw2])
