from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from fantasy import rules


def make_player(position, team_id, price='5.0'):
    return SimpleNamespace(
        position=position,
        team_id=team_id,
        team=SimpleNamespace(short_name=f'T{team_id}'),
        price=Decimal(price),
    )


def valid_squad():
    """2 GKP, 5 DEF, 5 MID, 3 FWD spread over 8 clubs, 5.0m each (75m total)."""
    squad = []
    club = 1
    for position, count in rules.POSITION_LIMITS.items():
        for _ in range(count):
            squad.append(make_player(position, club))
            club = club % 8 + 1
    return squad


def make_xi(gkp=1, defs=4, mids=4, fwds=2):
    players = []
    for position, count in (('GKP', gkp), ('DEF', defs), ('MID', mids), ('FWD', fwds)):
        for i in range(count):
            players.append(make_player(position, i + 1))
    return players


class SquadRulesTests(SimpleTestCase):
    def test_valid_squad_has_no_errors(self):
        self.assertEqual(rules.validate_squad(valid_squad()), [])

    def test_squad_must_have_15_players(self):
        errors = rules.validate_squad(valid_squad()[:14])
        self.assertTrue(any('exactly 15' in e for e in errors))

    def test_wrong_position_balance(self):
        squad = valid_squad()
        squad[0].position = 'FWD'  # now 1 goalkeeper and 4 forwards
        errors = rules.validate_squad(squad)
        self.assertTrue(any('goalkeeper' in e for e in errors))

    def test_max_three_players_per_club(self):
        squad = valid_squad()
        for player in squad[:4]:
            player.team_id = 99
            player.team.short_name = 'XXX'
        errors = rules.validate_squad(squad)
        self.assertTrue(any('one club' in e for e in errors))

    def test_three_players_from_one_club_is_fine(self):
        squad = valid_squad()
        for player in squad[:3]:
            player.team_id = 99
        self.assertEqual(rules.validate_squad(squad), [])

    def test_over_budget(self):
        squad = valid_squad()
        squad[0].price = Decimal('60.0')
        errors = rules.validate_squad(squad)
        self.assertTrue(any('budget' in e for e in errors))

    def test_exactly_100m_is_allowed(self):
        squad = valid_squad()
        squad[0].price = Decimal('30.0')  # 30 + 14 * 5 = 100
        self.assertEqual(rules.validate_squad(squad), [])


class StartingXITests(SimpleTestCase):
    def test_four_four_two_is_valid(self):
        self.assertEqual(rules.validate_starting_xi(make_xi(1, 4, 4, 2)), [])

    def test_three_four_three_is_valid(self):
        self.assertEqual(rules.validate_starting_xi(make_xi(1, 3, 4, 3)), [])

    def test_needs_eleven_players(self):
        errors = rules.validate_starting_xi(make_xi(1, 4, 4, 1))
        self.assertTrue(any('exactly 11' in e for e in errors))

    def test_only_one_goalkeeper(self):
        errors = rules.validate_starting_xi(make_xi(2, 3, 4, 2))
        self.assertTrue(any('goalkeeper' in e for e in errors))

    def test_at_least_three_defenders(self):
        errors = rules.validate_starting_xi(make_xi(1, 2, 5, 3))
        self.assertTrue(any('defenders' in e for e in errors))

    def test_formation_label(self):
        self.assertEqual(rules.formation(make_xi(1, 3, 5, 2)), '3-5-2')
        self.assertEqual(rules.formation([]), '')


class CaptainTests(SimpleTestCase):
    def test_valid_captains(self):
        self.assertEqual(rules.validate_captains(1, 2, {1, 2, 3}), [])

    def test_captain_and_vice_must_differ(self):
        self.assertTrue(rules.validate_captains(1, 1, {1, 2}))

    def test_captain_must_be_a_starter(self):
        self.assertTrue(rules.validate_captains(9, 2, {1, 2}))

    def test_both_must_be_chosen(self):
        self.assertTrue(rules.validate_captains(None, None, {1, 2}))