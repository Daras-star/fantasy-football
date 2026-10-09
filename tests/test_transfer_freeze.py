from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from fantasy.deadlines import snapshot_missing
from fantasy.models import FantasyTeam, GameweekScore, SquadPlayer
from fantasy.tasks import update_gameweek_scores
from players.models import Gameweek, Player, Position
from players.models import Team as Club


class FreezeTransferTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.gw1 = Gameweek.objects.create(
            number=1, name='Gameweek 1', deadline=now - timedelta(days=8)
        )
        self.gw2 = Gameweek.objects.create(
            number=2, name='Gameweek 2', deadline=now + timedelta(days=2)
        )
        club = Club.objects.create(fpl_id=1, name='Alpha FC', short_name='ALP')
        position = Position.objects.create(fpl_id=3, name='Midfielder', short_name='MID')
        self.players = [
            Player.objects.create(
                fpl_id=i, first_name='P', last_name=str(i), web_name=f'P{i}',
                team=club, position=position, price=Decimal('5.0'),
            )
            for i in range(1, 6)
        ]
        user = get_user_model().objects.create_user('tester', password='pass12345')
        self.team = FantasyTeam.objects.create(user=user, name='Test XI')
        self.set_squad(self.players[:3])
        snapshot_missing(self.team, include_before_joining=True)  # freezes gameweek 1

    def set_squad(self, players):
        SquadPlayer.objects.filter(fantasy_team=self.team).delete()
        SquadPlayer.objects.bulk_create(
            SquadPlayer(fantasy_team=self.team, player=p) for p in players
        )

    def close_gameweek_two(self):
        self.gw2.deadline = timezone.now() - timedelta(hours=1)
        self.gw2.save()
        snapshot_missing(self.team, include_before_joining=True)
        self.team.refresh_from_db()
        return GameweekScore.objects.get(fantasy_team=self.team, gameweek=self.gw2)

    def test_the_first_squad_is_free(self):
        score = GameweekScore.objects.get(fantasy_team=self.team, gameweek=self.gw1)
        self.assertEqual(score.transfer_cost, 0)

    def test_one_transfer_uses_the_free_one(self):
        self.set_squad([self.players[0], self.players[1], self.players[3]])
        score = self.close_gameweek_two()
        self.assertEqual(score.transfer_cost, 0)
        self.assertEqual(self.team.free_transfers, 1)

    def test_two_transfers_cost_four_points(self):
        self.set_squad([self.players[0], self.players[3], self.players[4]])
        score = self.close_gameweek_two()
        self.assertEqual(score.transfer_cost, 4)
        self.assertEqual(self.team.free_transfers, 1)

    def test_no_transfers_banks_a_free_one(self):
        score = self.close_gameweek_two()
        self.assertEqual(score.transfer_cost, 0)
        self.assertEqual(self.team.free_transfers, 2)

    def test_the_hit_is_taken_off_the_gameweek_points(self):
        self.set_squad([self.players[0], self.players[3], self.players[4]])
        score = self.close_gameweek_two()
        update_gameweek_scores(self.gw2)
        score.refresh_from_db()
        self.assertEqual(score.points, -4)