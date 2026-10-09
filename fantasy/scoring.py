"""Turns real match stats into fantasy points. Plain Python (no database)."""
from .rules import position_of
from .substitutions import auto_substitutions

# Points for a goal, by position
GOAL_POINTS = {'GKP': 6, 'DEF': 6, 'MID': 5, 'FWD': 4}

# Points for a clean sheet (the player must play 60+ minutes)
CLEAN_SHEET_POINTS = {'GKP': 4, 'DEF': 4, 'MID': 1, 'FWD': 0}

POINTS_UNDER_60_MINUTES = 1
POINTS_60_PLUS_MINUTES = 2
ASSIST_POINTS = 3

SAVES_PER_POINT = 3            # goalkeepers: 1 point for every 3 saves
GOALS_CONCEDED_PER_POINT = 2   # goalkeepers and defenders: -1 for every 2 goals conceded
PENALTY_SAVE_POINTS = 5
PENALTY_MISS_POINTS = -2
YELLOW_CARD_POINTS = -1
RED_CARD_POINTS = -3
OWN_GOAL_POINTS = -2

# Defensive contribution: 2 points for reaching the threshold (goalkeepers can't earn it)
DEFENSIVE_CONTRIBUTION_THRESHOLD = {'DEF': 10, 'MID': 12, 'FWD': 12}
DEFENSIVE_CONTRIBUTION_POINTS = 2

CAPTAIN_MULTIPLIER = 2
TRIPLE_CAPTAIN_MULTIPLIER = 3

# Chip codes (see fantasy/chips.py)
TRIPLE_CAPTAIN = 'TC'
BENCH_BOOST = 'BB'


def calculate_player_points(position, stats):
    """Fantasy points for one player in ONE match.

    `position` is a code such as 'DEF'. `stats` is a PlayerFixtureStats row
    (or anything with the same attributes).
    """
    if stats.minutes <= 0:
        return 0

    points = POINTS_60_PLUS_MINUTES if stats.minutes >= 60 else POINTS_UNDER_60_MINUTES
    points += stats.goals_scored * GOAL_POINTS[position]
    points += stats.assists * ASSIST_POINTS

    if stats.clean_sheets > 0 and stats.minutes >= 60:
        points += CLEAN_SHEET_POINTS[position]

    if position in ('GKP', 'DEF'):
        points -= stats.goals_conceded // GOALS_CONCEDED_PER_POINT

    if position == 'GKP':
        points += stats.saves // SAVES_PER_POINT

    threshold = DEFENSIVE_CONTRIBUTION_THRESHOLD.get(position)
    if threshold is not None and stats.defensive_contribution >= threshold:
        points += DEFENSIVE_CONTRIBUTION_POINTS

    points += stats.penalties_saved * PENALTY_SAVE_POINTS
    points += stats.penalties_missed * PENALTY_MISS_POINTS
    points += stats.yellow_cards * YELLOW_CARD_POINTS
    points += stats.red_cards * RED_CARD_POINTS
    points += stats.own_goals * OWN_GOAL_POINTS
    points += stats.bonus

    return points


def calculate_gameweek_points(position, matches):
    """A player's points for a whole gameweek: the sum of all their matches in it."""
    return sum(calculate_player_points(position, match) for match in matches)


def calculate_team_points(squad, stats_by_player_id, chip=None):
    """Total points for one fantasy team in one gameweek.

    squad: SquadPlayer or GameweekPick objects for the team.
    stats_by_player_id: {player_id: [match stats, ...]} for that gameweek.
    chip: the chip played that gameweek ('TC' or 'BB'), or None.

    Starters score, and bench players replace any starter who didn't play
    (see substitutions.py). With Bench Boost the whole bench scores instead.
    The captain's points are doubled (tripled with Triple Captain). If the
    captain didn't play, the vice-captain gets the bonus instead.
    """
    squad = list(squad)

    def played(entry):
        return any(m.minutes > 0 for m in stats_by_player_id.get(entry.player_id, []))

    captain = next((e for e in squad if e.is_captain), None)
    vice_captain = next((e for e in squad if e.is_vice_captain), None)

    if captain is not None and played(captain):
        boosted = captain
    elif vice_captain is not None and played(vice_captain):
        boosted = vice_captain
    else:
        boosted = None

    multiplier = TRIPLE_CAPTAIN_MULTIPLIER if chip == TRIPLE_CAPTAIN else CAPTAIN_MULTIPLIER

    if chip == BENCH_BOOST:
        scoring_entries = squad
    else:
        scoring_entries, _ = auto_substitutions(squad, played)

    total = 0
    for entry in scoring_entries:
        matches = stats_by_player_id.get(entry.player_id, [])
        points = calculate_gameweek_points(position_of(entry.player), matches)
        if entry is boosted:
            points *= multiplier
        total += points

    return total