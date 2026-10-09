from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from players.models import Fixture, Gameweek
from players.models import Team as Club
from players.standings import build_table

TEAMS = {1: 'Alpha', 2: 'Beta', 3: 'Gamma'}


class BuildTableTests(SimpleTestCase):
    def test_points_and_ordering(self):
        results = [(1, 2, 2, 0), (2, 3, 1, 1), (3, 1, 0, 3)]
        table = build_table(TEAMS, results)
        self.assertEqual([r['name'] for r in table], ['Alpha', 'Beta', 'Gamma'])
        alpha, beta, gamma = table
        self.assertEqual(
            (alpha['played'], alpha['won'], alpha['points'], alpha['goal_difference']),
            (2, 2, 6, 5),
        )
        self.assertEqual((beta['points'], beta['goal_difference']), (1, -2))
        self.assertEqual((gamma['points'], gamma['goal_difference']), (1, -3))
        self.assertEqual([r['position'] for r in table], [1, 2, 3])

    def test_no_results_orders_by_name(self):
        table = build_table(TEAMS, [])
        self.assertEqual([r['name'] for r in table], ['Alpha', 'Beta', 'Gamma'])
        self.assertTrue(all(r['played'] == 0 for r in table))

    def test_goals_scored_breaks_a_tie(self):
        # Alpha wins 1-0 and Beta wins 3-2: same points and goal difference, Beta scored more
        results = [(1, 3, 1, 0), (2, 3, 3, 2)]
        table = build_table(TEAMS, results)
        self.assertEqual([r['name'] for r in table][:2], ['Beta', 'Alpha'])

    def test_form_is_the_last_five_oldest_first(self):
        results = [(1, 2, 1, 0), (1, 2, 1, 0), (1, 2, 1, 0), (1, 2, 0, 1), (1, 2, 1, 1), (1, 2, 2, 2)]
        row = {r['team_id']: r for r in build_table(TEAMS, results)}[1]
        self.assertEqual(row['form'], ['W', 'W', 'L', 'D', 'D'])
        self.assertEqual(row['played'], 6)

    def test_venue_filters(self):
        results = [(1, 2, 3, 0), (2, 1, 1, 0)]
        home = {r['team_id']: r for r in build_table(TEAMS, results, 'home')}
        self.assertEqual((home[1]['played'], home[1]['points']), (1, 3))
        self.assertEqual((home[2]['played'], home[2]['points']), (1, 3))
        self.assertEqual(home[3]['played'], 0)
        away = {r['team_id']: r for r in build_table(TEAMS, results, 'away')}
        self.assertEqual((away[1]['played'], away[1]['lost']), (1, 1))
        self.assertEqual((away[2]['played'], away[2]['lost']), (1, 1))


class TableViewTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.alpha = Club.objects.create(fpl_id=1, name='Alpha FC', short_name='ALP')
        self.beta = Club.objects.create(fpl_id=2, name='Beta FC', short_name='BET')
        gw1 = Gameweek.objects.create(
            number=1, name='Gameweek 1', deadline=now - timedelta(days=30), finished=True
        )
        gw2 = Gameweek.objects.create(
            number=2, name='Gameweek 2', deadline=now + timedelta(days=3)
        )
        Fixture.objects.create(
            fpl_id=1, gameweek=gw1, home_team=self.alpha, away_team=self.beta,
            kickoff=now - timedelta(days=28), home_score=2, away_score=1,
            started=True, finished=True,
        )
        Fixture.objects.create(
            fpl_id=2, gameweek=gw2, home_team=self.beta, away_team=self.alpha,
            kickoff=now + timedelta(days=5),
        )

    def rows(self, query=''):
        response = self.client.get(reverse('players:table') + query)
        self.assertEqual(response.status_code, 200)
        return {row['team'].short_name: row for row in response.context['table']}

    def test_only_finished_matches_count(self):
        rows = self.rows()
        self.assertEqual((rows['ALP']['position'], rows['ALP']['points']), (1, 3))
        self.assertEqual((rows['BET']['position'], rows['BET']['points']), (2, 0))
        self.assertEqual(rows['ALP']['played'], 1)
        self.assertEqual(rows['ALP']['form'], ['W'])

    def test_next_fixture(self):
        rows = self.rows()
        self.assertEqual(rows['ALP']['next'], (self.beta, 'A'))
        self.assertEqual(rows['BET']['next'], (self.alpha, 'H'))

    def test_away_filter(self):
        rows = self.rows('?venue=away')
        self.assertEqual(rows['ALP']['played'], 0)
        self.assertEqual((rows['BET']['played'], rows['BET']['lost']), (1, 1))

    def test_gameweek_filter(self):
        rows = self.rows('?gw=1')
        self.assertEqual(rows['ALP']['played'], 1)
        self.assertEqual(rows['ALP']['next'], (self.beta, 'A'))

    def test_unknown_filters_fall_back(self):
        self.rows('?venue=nonsense&gw=999')