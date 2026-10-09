from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from fantasy.deadlines import last_frozen_player_ids, snapshot_missing
from fantasy.models import ChipPlay, FantasyTeam, GameweekScore, SquadPlayer
from players.models import Gameweek, Player, Position
from players.models import Team as Club


class FreeHitAndWildcardTests(TestCase):
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
        self.original_ids = {p.id for p in self.players[:3]}
        self.hit_ids = {p.id for p in self.players[2:5]}

    def set_squad(self, players):
        SquadPlayer.objects.filter(fantasy_team=self.team).delete()
        SquadPlayer.objects.bulk_create(
            SquadPlayer(fantasy_team=self.team, player=p) for p in players
        )

    def squad_ids(self):
        return set(SquadPlayer.objects.filter(fantasy_team=self.team).values_list('player_id', flat=True))

    def play(self, chip):
        ChipPlay.objects.create(fantasy_team=self.team, gameweek=self.gw2, chip=chip)

    def close_gameweek_two(self):
        self.gw2.deadline = timezone.now() - timedelta(hours=1)
        self.gw2.save()
        snapshot_missing(self.team, include_before_joining=True)
        self.team.refresh_from_db()
        return GameweekScore.objects.get(fantasy_team=self.team, gameweek=self.gw2)

    def test_free_hit_costs_nothing_and_keeps_the_free_transfer(self):
        self.play('FH')
        self.set_squad(self.players[2:5])
        score = self.close_gameweek_two()
        self.assertEqual(score.transfer_cost, 0)
        self.assertEqual(self.team.free_transfers, 2)

    def test_the_free_hit_squad_is_what_gets_scored(self):
        self.play('FH')
        self.set_squad(self.players[2:5])
        score = self.close_gameweek_two()
        self.assertEqual({pick.player_id for pick in score.picks.all()}, self.hit_ids)

    def test_the_squad_goes_back_after_a_free_hit(self):
        self.play('FH')
        self.set_squad(self.players[2:5])
        self.close_gameweek_two()
        self.assertEqual(self.squad_ids(), self.original_ids)

    def test_a_free_hit_gameweek_is_not_the_starting_point_for_later_transfers(self):
        self.play('FH')
        self.set_squad(self.players[2:5])
        self.close_gameweek_two()
        self.assertEqual(last_frozen_player_ids(self.team), self.original_ids)

    def test_wildcard_costs_nothing_and_the_new_squad_stays(self):
        self.play('WC')
        self.set_squad(self.players[2:5])
        score = self.close_gameweek_two()
        self.assertEqual(score.transfer_cost, 0)
        self.assertEqual(self.team.free_transfers, 2)
        self.assertEqual(self.squad_ids(), self.hit_ids)
        self.assertEqual(last_frozen_player_ids(self.team), self.hit_ids)

    def test_cancelling_a_free_hit_restores_the_squad(self):
        self.client.login(username='tester', password='pass12345')
        self.play('FH')
        self.set_squad(self.players[2:5])
        self.client.post(reverse('cancel_chip'))
        self.assertFalse(ChipPlay.objects.exists())
        self.assertEqual(self.squad_ids(), self.original_ids)