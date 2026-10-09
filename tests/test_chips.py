from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from fantasy.chips import chip_states, window_of
from fantasy.models import ChipPlay, FantasyTeam, GameweekPick, GameweekScore, SquadPlayer
from fantasy.tasks import update_gameweek_scores
from players.models import Fixture, Gameweek, Player, PlayerFixtureStats, Position
from players.models import Team as Club


class ChipStateTests(SimpleTestCase):
    def test_everything_is_available_from_gameweek_two(self):
        states = chip_states([], 2)
        self.assertEqual({s['state'] for s in states.values()}, {'available'})

    def test_wildcard_and_free_hit_are_not_available_in_gameweek_one(self):
        states = chip_states([], 1)
        self.assertEqual(states['WC']['state'], 'early')
        self.assertEqual(states['FH']['state'], 'early')
        self.assertEqual(states['TC']['state'], 'available')

    def test_free_hit_cannot_be_played_two_gameweeks_in_a_row(self):
        self.assertEqual(chip_states([('FH', 19)], 20)['FH']['state'], 'cooldown')
        self.assertEqual(chip_states([('FH', 19)], 21)['FH']['state'], 'available')

    def test_wildcard_comes_back_in_the_second_half(self):
        self.assertEqual(chip_states([('WC', 19)], 20)['WC']['state'], 'available')

    def test_an_active_chip_blocks_the_other(self):
        states = chip_states([('TC', 5)], 5)
        self.assertEqual(states['TC']['state'], 'active')
        self.assertEqual(states['BB']['state'], 'blocked')

    def test_a_chip_used_earlier_in_the_same_half_is_unavailable(self):
        states = chip_states([('TC', 3)], 7)
        self.assertEqual(states['TC'], {'state': 'used', 'used_in': 3})
        self.assertEqual(states['BB']['state'], 'available')

    def test_chips_come_back_in_the_second_half(self):
        self.assertEqual(chip_states([('TC', 3)], 20)['TC']['state'], 'available')
        self.assertEqual(chip_states([('TC', 19)], 20)['TC']['state'], 'available')

    def test_a_second_half_use_blocks_later_second_half_gameweeks(self):
        self.assertEqual(chip_states([('BB', 22)], 30)['BB']['state'], 'used')

    def test_windows(self):
        self.assertEqual(window_of(1), 0)
        self.assertEqual(window_of(19), 0)
        self.assertEqual(window_of(20), 1)
        self.assertEqual(window_of(38), 1)
        self.assertIsNone(window_of(39))


class ChipViewTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.gw1 = Gameweek.objects.create(
            number=1, name='Gameweek 1', deadline=now - timedelta(days=20)
        )
        self.gw2 = Gameweek.objects.create(
            number=2, name='Gameweek 2', deadline=now + timedelta(days=3)
        )

        club = Club.objects.create(fpl_id=1, name='Alpha FC', short_name='ALP')
        position = Position.objects.create(fpl_id=3, name='Midfielder', short_name='MID')
        players = [
            Player.objects.create(
                fpl_id=i, first_name='P', last_name=str(i), web_name=f'P{i}',
                team=club, position=position, price=Decimal('5.0'),
            )
            for i in range(1, 16)
        ]

        user = get_user_model().objects.create_user('tester', password='pass12345')
        self.team = FantasyTeam.objects.create(user=user, name='Test XI')
        SquadPlayer.objects.bulk_create(
            SquadPlayer(
                fantasy_team=self.team, player=p, is_starter=index < 11,
                is_captain=index == 0, is_vice_captain=index == 1,
            )
            for index, p in enumerate(players)
        )
        self.client.login(username='tester', password='pass12345')

    def play(self, code):
        return self.client.post(reverse('play_chip'), {'chip': code})

    def test_chips_page_loads(self):
        self.assertEqual(self.client.get(reverse('chips')).status_code, 200)

    def test_play_a_chip(self):
        self.play('TC')
        play = ChipPlay.objects.get()
        self.assertEqual((play.chip, play.gameweek), ('TC', self.gw2))

    def test_chips_need_a_full_lineup(self):
        SquadPlayer.objects.filter(fantasy_team=self.team).update(is_starter=False)
        self.play('TC')
        self.assertFalse(ChipPlay.objects.exists())

    def test_only_one_chip_per_gameweek(self):
        self.play('TC')
        self.play('BB')
        self.assertEqual(list(ChipPlay.objects.values_list('chip', flat=True)), ['TC'])

    def test_unknown_chip_is_rejected(self):
        self.play('XX')
        self.assertFalse(ChipPlay.objects.exists())

    def test_cancel_a_chip(self):
        self.play('BB')
        self.client.post(reverse('cancel_chip'))
        self.assertFalse(ChipPlay.objects.exists())

    def test_a_chip_already_used_this_half_is_refused(self):
        ChipPlay.objects.create(fantasy_team=self.team, gameweek=self.gw1, chip='TC')
        self.play('TC')
        self.assertFalse(ChipPlay.objects.filter(gameweek=self.gw2).exists())


class ChipScoringTests(TestCase):
    def build(self, chip):
        """A captain who scores a goal, plus a bench player who scores a goal."""
        gw = Gameweek.objects.create(
            number=3, name='Gameweek 3', deadline=timezone.now() - timedelta(days=1)
        )
        club = Club.objects.create(fpl_id=1, name='Alpha FC', short_name='ALP')
        other = Club.objects.create(fpl_id=2, name='Beta FC', short_name='BET')
        forward = Position.objects.create(fpl_id=4, name='Forward', short_name='FWD')
        captain = Player.objects.create(
            fpl_id=1, first_name='A', last_name='Captain', web_name='Captain',
            team=club, position=forward, price=Decimal('8.0'),
        )
        bench = Player.objects.create(
            fpl_id=2, first_name='B', last_name='Bench', web_name='Bench',
            team=club, position=forward, price=Decimal('4.5'),
        )
        fixture = Fixture.objects.create(fpl_id=1, gameweek=gw, home_team=club, away_team=other)
        for player in (captain, bench):
            PlayerFixtureStats.objects.create(
                player=player, fixture=fixture, minutes=90, goals_scored=1
            )

        user = get_user_model().objects.create_user('tester', password='pass12345')
        team = FantasyTeam.objects.create(user=user, name='Test XI')
        score = GameweekScore.objects.create(fantasy_team=team, gameweek=gw)
        GameweekPick.objects.create(score=score, player=captain, is_starter=True, is_captain=True)
        GameweekPick.objects.create(score=score, player=bench, is_starter=False)
        if chip:
            ChipPlay.objects.create(fantasy_team=team, gameweek=gw, chip=chip)

        update_gameweek_scores(gw)
        score.refresh_from_db()
        return score.points

    def test_no_chip(self):
        # captain: (2 + 4) * 2 = 12, bench player doesn't count
        self.assertEqual(self.build(None), 12)

    def test_triple_captain_is_applied_when_scoring(self):
        self.assertEqual(self.build('TC'), (2 + 4) * 3)

    def test_bench_boost_is_applied_when_scoring(self):
        # captain 12 + bench player (2 + 4) = 18
        self.assertEqual(self.build('BB'), 18)