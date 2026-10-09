from types import SimpleNamespace

from django.test import SimpleTestCase

from fantasy.substitutions import auto_substitutions


def entry(player_id, position, starter=True):
    return SimpleNamespace(
        player_id=player_id, player=SimpleNamespace(position=position), is_starter=starter
    )


def make_squad():
    starters = (
        [entry(1, 'GKP')]
        + [entry(i, 'DEF') for i in (2, 3, 4)]
        + [entry(i, 'MID') for i in (5, 6, 7, 8)]
        + [entry(i, 'FWD') for i in (9, 10, 11)]
    )
    bench = [
        entry(12, 'GKP', False), entry(13, 'DEF', False),
        entry(14, 'MID', False), entry(15, 'FWD', False),
    ]
    return starters + bench


def run(did_not_play):
    lineup, swaps = auto_substitutions(
        make_squad(), lambda e: e.player_id not in did_not_play
    )
    return (
        sorted(e.player_id for e in lineup),
        [(out.player_id, sub.player_id) for out, sub in swaps],
    )


class AutoSubstitutionTests(SimpleTestCase):
    def test_nothing_changes_when_everyone_plays(self):
        lineup, swaps = run(set())
        self.assertEqual(lineup, list(range(1, 12)))
        self.assertEqual(swaps, [])

    def test_the_first_bench_outfielder_replaces_a_missing_starter(self):
        self.assertEqual(run({5})[1], [(5, 13)])

    def test_a_bench_player_who_didnt_play_is_skipped(self):
        self.assertEqual(run({5, 13})[1], [(5, 14)])

    def test_the_backup_goalkeeper_replaces_the_goalkeeper(self):
        self.assertEqual(run({1})[1], [(1, 12)])

    def test_an_outfielder_cannot_replace_the_goalkeeper(self):
        lineup, swaps = run({1, 12})
        self.assertEqual(swaps, [])
        self.assertIn(1, lineup)

    def test_a_swap_that_breaks_the_formation_is_refused(self):
        # Only 3 defenders start, so a midfielder or forward cannot replace one
        self.assertEqual(run({2, 13})[1], [])

    def test_two_missing_starters_get_two_replacements(self):
        self.assertEqual(run({5, 6})[1], [(5, 13), (6, 14)])

    def test_no_replacement_when_the_whole_bench_missed_out(self):
        self.assertEqual(run({5, 12, 13, 14, 15})[1], [])