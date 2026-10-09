from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from fantasy.models import FantasyTeam, SquadPlayer
from fantasy.ranking import assign_ranks, overall_rank
from players.models import Player, Position
from players.models import Team as Club


class AssignRanksTests(SimpleTestCase):
    def test_ties_share_a_rank(self):
        rows = assign_ranks([('a', 50), ('b', 40), ('c', 40), ('d', 10)])
        self.assertEqual([row['rank'] for row in rows], [1, 2, 2, 4])

    def test_empty_list(self):
        self.assertEqual(assign_ranks([]), [])


class OverallRankTests(TestCase):
    def setUp(self):
        club = Club.objects.create(fpl_id=1, name='Alpha FC', short_name='ALP')
        position = Position.objects.create(fpl_id=3, name='Midfielder', short_name='MID')
        self.players = [
            Player.objects.create(
                fpl_id=i, first_name='P', last_name=str(i), web_name=f'P{i}',
                team=club, position=position, price=Decimal('5.0'),
            )
            for i in range(1, 16)
        ]

    def make_team(self, name, points, full=True):
        user = get_user_model().objects.create_user(name, password='pass12345')
        team = FantasyTeam.objects.create(user=user, name=name, total_points=points)
        chosen = self.players if full else self.players[:5]
        SquadPlayer.objects.bulk_create(SquadPlayer(fantasy_team=team, player=p) for p in chosen)
        return team

    def test_rank_counts_teams_with_more_points(self):
        a = self.make_team('a', 50)
        b = self.make_team('b', 30)
        c = self.make_team('c', 30)
        self.assertEqual(overall_rank(a), (1, 3))
        self.assertEqual(overall_rank(b), (2, 3))
        self.assertEqual(overall_rank(c), (2, 3))

    def test_team_without_a_full_squad_is_not_ranked(self):
        a = self.make_team('a', 50)
        d = self.make_team('d', 99, full=False)
        self.assertIsNone(overall_rank(d))
        self.assertEqual(overall_rank(a), (1, 1))