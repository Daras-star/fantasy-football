from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from fantasy.bank import get_bank
from fantasy.models import FantasyTeam, SquadPlayer
from players.models import Gameweek, Player, Position
from players.models import Team as Club


class BankTests(TestCase):
    def setUp(self):
        Gameweek.objects.create(
            number=1, name='Gameweek 1', deadline=timezone.now() + timedelta(days=3)
        )
        positions = {
            code: Position.objects.create(fpl_id=i, name=code, short_name=code)
            for i, code in enumerate(['GKP', 'DEF', 'MID', 'FWD'], start=1)
        }
        clubs = [
            Club.objects.create(fpl_id=i, name=f'Club {i}', short_name=f'C{i}')
            for i in range(1, 6)
        ]
        layout = ['GKP'] * 2 + ['DEF'] * 5 + ['MID'] * 5 + ['FWD'] * 3
        self.players = [
            Player.objects.create(
                fpl_id=index + 1, first_name='P', last_name=str(index), web_name=f'P{index}',
                team=clubs[index % 5], position=positions[code], price=Decimal('5.0'),
            )
            for index, code in enumerate(layout)
        ]
        user = get_user_model().objects.create_user('tester', password='pass12345')
        self.team = FantasyTeam.objects.create(user=user, name='Test XI')
        self.client.login(username='tester', password='pass12345')

    def fill_squad(self, bank, bought_price):
        self.team.bank = bank
        self.team.save()
        SquadPlayer.objects.bulk_create(
            SquadPlayer(fantasy_team=self.team, player=p, bought_price=bought_price)
            for p in self.players
        )

    def swap_for(self, price):
        """Swap the last forward, whose price has risen to 6.0, for a new forward."""
        rising = self.players[14]
        rising.price = Decimal('6.0')
        rising.save()
        replacement = Player.objects.create(
            fpl_id=100, first_name='R', last_name='New', web_name='New',
            team=rising.team, position=rising.position, price=Decimal(price),
        )
        ids = [p.id for p in self.players[:14]] + [replacement.id]
        response = self.client.post(
            reverse('pick_squad'), {'players': ids, 'team_name': 'Test XI'}
        )
        return response, rising, replacement

    def test_older_teams_get_their_bank_worked_out(self):
        self.fill_squad(None, None)
        self.assertEqual(get_bank(self.team), Decimal('25.0'))
        self.assertFalse(SquadPlayer.objects.filter(bought_price__isnull=True).exists())

    def test_a_new_team_starts_with_the_full_budget(self):
        self.assertEqual(get_bank(self.team), Decimal('100.0'))

    def test_you_only_keep_half_of_a_price_rise(self):
        # Bought at 5.0, now 6.0, so he sells for 5.5. A 5.6 replacement is too much.
        self.fill_squad(Decimal('0.0'), Decimal('5.0'))
        response, rising, _ = self.swap_for('5.6')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SquadPlayer.objects.filter(player=rising).exists())

    def test_a_replacement_you_can_afford_is_accepted(self):
        self.fill_squad(Decimal('0.0'), Decimal('5.0'))
        response, rising, replacement = self.swap_for('5.5')
        self.assertEqual(response.status_code, 302)
        self.team.refresh_from_db()
        self.assertEqual(self.team.bank, Decimal('0.0'))
        self.assertFalse(SquadPlayer.objects.filter(player=rising).exists())
        bought = SquadPlayer.objects.get(player=replacement)
        self.assertEqual(bought.bought_price, Decimal('5.5'))