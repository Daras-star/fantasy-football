from types import SimpleNamespace

from django.test import SimpleTestCase

from fantasy.scoring import (
    calculate_gameweek_points,
    calculate_player_points,
    calculate_team_points,
)


def make_stats(**overrides):
    stats = dict(
        minutes=90, goals_scored=0, assists=0, clean_sheets=0, goals_conceded=0,
        saves=0, penalties_saved=0, penalties_missed=0, yellow_cards=0, red_cards=0,
        own_goals=0, bonus=0, defensive_contribution=0,
    )
    stats.update(overrides)
    return SimpleNamespace(**stats)


def make_entry(player_id, position, starter=True, captain=False, vice=False):
    return SimpleNamespace(
        player_id=player_id,
        player=SimpleNamespace(position=position),
        is_starter=starter,
        is_captain=captain,
        is_vice_captain=vice,
    )


class PlayerPointsTests(SimpleTestCase):
    def test_did_not_play(self):
        self.assertEqual(calculate_player_points('FWD', make_stats(minutes=0)), 0)

    def test_appearance_points(self):
        self.assertEqual(calculate_player_points('FWD', make_stats(minutes=45)), 1)
        self.assertEqual(calculate_player_points('FWD', make_stats(minutes=60)), 2)
        self.assertEqual(calculate_player_points('FWD', make_stats(minutes=90)), 2)

    def test_goals_depend_on_position(self):
        self.assertEqual(calculate_player_points('FWD', make_stats(goals_scored=1)), 2 + 4)
        self.assertEqual(calculate_player_points('MID', make_stats(goals_scored=1)), 2 + 5)
        self.assertEqual(calculate_player_points('DEF', make_stats(goals_scored=1)), 2 + 6)
        self.assertEqual(calculate_player_points('GKP', make_stats(goals_scored=1)), 2 + 6)

    def test_assists(self):
        self.assertEqual(calculate_player_points('MID', make_stats(assists=2)), 2 + 6)

    def test_clean_sheets(self):
        self.assertEqual(calculate_player_points('GKP', make_stats(clean_sheets=1)), 2 + 4)
        self.assertEqual(calculate_player_points('DEF', make_stats(clean_sheets=1)), 2 + 4)
        self.assertEqual(calculate_player_points('MID', make_stats(clean_sheets=1)), 2 + 1)
        self.assertEqual(calculate_player_points('FWD', make_stats(clean_sheets=1)), 2)

    def test_clean_sheet_needs_60_minutes(self):
        stats = make_stats(minutes=45, clean_sheets=1)
        self.assertEqual(calculate_player_points('DEF', stats), 1)

    def test_goals_conceded_only_costs_gkp_and_def(self):
        self.assertEqual(calculate_player_points('DEF', make_stats(goals_conceded=1)), 2)
        self.assertEqual(calculate_player_points('DEF', make_stats(goals_conceded=3)), 2 - 1)
        self.assertEqual(calculate_player_points('GKP', make_stats(goals_conceded=4)), 2 - 2)
        self.assertEqual(calculate_player_points('MID', make_stats(goals_conceded=4)), 2)

    def test_goalkeeper_saves_and_penalty_save(self):
        self.assertEqual(calculate_player_points('GKP', make_stats(saves=7)), 2 + 2)
        self.assertEqual(calculate_player_points('GKP', make_stats(penalties_saved=1)), 2 + 5)

    def test_cards_own_goals_and_missed_penalties(self):
        self.assertEqual(calculate_player_points('MID', make_stats(yellow_cards=1)), 2 - 1)
        self.assertEqual(calculate_player_points('MID', make_stats(red_cards=1)), 2 - 3)
        self.assertEqual(calculate_player_points('MID', make_stats(own_goals=1)), 2 - 2)
        self.assertEqual(calculate_player_points('MID', make_stats(penalties_missed=1)), 2 - 2)

    def test_bonus_points(self):
        self.assertEqual(calculate_player_points('FWD', make_stats(bonus=3)), 2 + 3)

    def test_defensive_contribution(self):
        self.assertEqual(calculate_player_points('DEF', make_stats(defensive_contribution=10)), 2 + 2)
        self.assertEqual(calculate_player_points('DEF', make_stats(defensive_contribution=9)), 2)
        self.assertEqual(calculate_player_points('MID', make_stats(defensive_contribution=11)), 2)
        self.assertEqual(calculate_player_points('MID', make_stats(defensive_contribution=12)), 2 + 2)
        self.assertEqual(calculate_player_points('GKP', make_stats(defensive_contribution=20)), 2)


class GameweekPointsTests(SimpleTestCase):
    def test_double_gameweek_adds_both_matches(self):
        matches = [make_stats(goals_scored=1), make_stats()]
        self.assertEqual(calculate_gameweek_points('FWD', matches), (2 + 4) + 2)

    def test_no_matches_is_zero(self):
        self.assertEqual(calculate_gameweek_points('FWD', []), 0)


class TeamPointsTests(SimpleTestCase):
    def test_captain_points_are_doubled(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID')]
        stats = {1: [make_stats(goals_scored=1)], 2: [make_stats()]}
        # captain: (2 + 4) * 2 = 12, midfielder: 2
        self.assertEqual(calculate_team_points(squad, stats), 14)

    def test_bench_players_do_not_score(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID', starter=False)]
        stats = {1: [make_stats()], 2: [make_stats(goals_scored=3)]}
        self.assertEqual(calculate_team_points(squad, stats), 4)

    def test_vice_captain_takes_over_if_captain_did_not_play(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID', vice=True)]
        stats = {1: [make_stats(minutes=0)], 2: [make_stats()]}
        self.assertEqual(calculate_team_points(squad, stats), 4)

    def test_vice_captain_takes_over_if_captain_has_no_stats(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID', vice=True)]
        stats = {2: [make_stats()]}
        self.assertEqual(calculate_team_points(squad, stats), 4)

    def test_captain_in_a_double_gameweek(self):
        squad = [make_entry(1, 'FWD', captain=True)]
        stats = {1: [make_stats(goals_scored=1), make_stats()]}
        self.assertEqual(calculate_team_points(squad, stats), (6 + 2) * 2)
class ChipPointsTests(SimpleTestCase):
    def test_triple_captain_triples_the_captain(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID')]
        stats = {1: [make_stats(goals_scored=1)], 2: [make_stats()]}
        # captain: (2 + 4) * 3 = 18, midfielder: 2
        self.assertEqual(calculate_team_points(squad, stats, chip='TC'), 20)

    def test_triple_captain_passes_to_the_vice_captain(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID', vice=True)]
        stats = {1: [make_stats(minutes=0)], 2: [make_stats()]}
        self.assertEqual(calculate_team_points(squad, stats, chip='TC'), 6)

    def test_bench_boost_counts_the_bench(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID', starter=False)]
        stats = {1: [make_stats()], 2: [make_stats(goals_scored=1)]}
        # captain: 2 * 2 = 4, bench midfielder: 2 + 5 = 7
        self.assertEqual(calculate_team_points(squad, stats, chip='BB'), 11)

    def test_the_bench_is_left_out_without_bench_boost(self):
        squad = [make_entry(1, 'FWD', captain=True), make_entry(2, 'MID', starter=False)]
        stats = {1: [make_stats()], 2: [make_stats(goals_scored=1)]}
        self.assertEqual(calculate_team_points(squad, stats, chip=None), 4)
class AutoSubPointsTests(SimpleTestCase):
    def points(self, starter_minutes):
        """A full squad where one midfielder (id 6) may miss the match.

        Only bench midfielder 14 plays, and he scores a goal (2 + 5 = 7).
        """
        positions = ['GKP'] + ['DEF'] * 4 + ['MID'] * 4 + ['FWD'] * 2
        squad = [
            make_entry(i + 1, pos, captain=(i == 9)) for i, pos in enumerate(positions)
        ]
        squad += [
            make_entry(12, 'GKP', starter=False), make_entry(13, 'DEF', starter=False),
            make_entry(14, 'MID', starter=False), make_entry(15, 'FWD', starter=False),
        ]
        stats = {i: [make_stats()] for i in range(1, 12)}
        stats[6] = [make_stats(minutes=starter_minutes)]
        stats.update({
            12: [make_stats(minutes=0)], 13: [make_stats(minutes=0)],
            14: [make_stats(goals_scored=1)], 15: [make_stats(minutes=0)],
        })
        return calculate_team_points(squad, stats)

    def test_a_substitute_scores_for_a_starter_who_didnt_play(self):
        # Without the sub the midfielder scores 2. With it, the bench midfielder's 7 counts.
        self.assertEqual(self.points(0) - self.points(90), 5)