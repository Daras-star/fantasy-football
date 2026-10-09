"""Game rules for a fantasy team. Plain Python (no database), so it is easy to test."""
from collections import Counter
from decimal import Decimal

BUDGET = Decimal('100.0')   # £100m
SQUAD_SIZE = 15
MAX_PER_CLUB = 3
STARTING_XI_SIZE = 11

# Exactly this many of each position in the 15-player squad
POSITION_LIMITS = {'GKP': 2, 'DEF': 5, 'MID': 5, 'FWD': 3}

# (minimum, maximum) of each position in the starting XI
FORMATION_LIMITS = {'GKP': (1, 1), 'DEF': (3, 5), 'MID': (2, 5), 'FWD': (1, 3)}

POSITION_NAMES = {
    'GKP': ('goalkeeper', 'goalkeepers'),
    'DEF': ('defender', 'defenders'),
    'MID': ('midfielder', 'midfielders'),
    'FWD': ('forward', 'forwards'),
}


def _count_text(count, position):
    singular, plural = POSITION_NAMES[position]
    return f"{count} {singular if count == 1 else plural}"
def position_of(player):
    """Position code ('GKP', 'DEF', 'MID', 'FWD') for a player.

    Works with a real Player (whose position is a database object) and with
    the plain stand-ins used in the tests.
    """
    position = player.position
    return getattr(position, 'short_name', position)


def validate_squad(players, check_budget=True):
    """Check a 15-player squad. Returns a list of error messages (empty list = valid)."""
    players = list(players)
    errors = []

    if len(players) != SQUAD_SIZE:
        errors.append(f"Pick exactly {SQUAD_SIZE} players (you picked {len(players)}).")

    by_position = Counter(position_of(p) for p in players)
    for position, required in POSITION_LIMITS.items():
        picked = by_position.get(position, 0)
        if picked != required:
            errors.append(
                f"You need exactly {_count_text(required, position)} (you picked {picked})."
            )

    by_club = Counter(p.team_id for p in players)
    for team_id, count in by_club.items():
        if count > MAX_PER_CLUB:
            club = next(p.team.short_name for p in players if p.team_id == team_id)
            errors.append(
                f"You can only have {MAX_PER_CLUB} players from one club ({club} has {count})."
            )

        if check_budget:
            total_cost = sum((p.price for p in players), Decimal('0.0'))
            if total_cost > BUDGET:
                errors.append(
                    f"Your squad costs £{total_cost}m, which is £{total_cost - BUDGET}m "
                    f"over the £{BUDGET}m budget."
            )

    return errors



def validate_starting_xi(starters):
    """Check the 11 starters follow the allowed formations. Returns a list of errors."""
    starters = list(starters)
    errors = []

    if len(starters) != STARTING_XI_SIZE:
        errors.append(f"Pick exactly {STARTING_XI_SIZE} starters (you picked {len(starters)}).")

    by_position = Counter(position_of(p) for p in starters)
    for position, (low, high) in FORMATION_LIMITS.items():
        picked = by_position.get(position, 0)
        if low <= picked <= high:
            continue
        if low == high:
            wanted = f"exactly {_count_text(low, position)}"
        else:
            wanted = f"between {low} and {high} {POSITION_NAMES[position][1]}"
        errors.append(f"Your starting XI needs {wanted} (you picked {picked}).")

    return errors


def validate_captains(captain_id, vice_captain_id, starter_ids):
    """Captain and vice-captain must be two different starters."""
    errors = []

    if captain_id is None:
        errors.append("Choose a captain.")
    elif captain_id not in starter_ids:
        errors.append("Your captain must be in your starting XI.")

    if vice_captain_id is None:
        errors.append("Choose a vice-captain.")
    elif vice_captain_id not in starter_ids:
        errors.append("Your vice-captain must be in your starting XI.")

    if captain_id is not None and captain_id == vice_captain_id:
        errors.append("Your captain and vice-captain must be different players.")

    return errors


def formation(players):
    """Return a lineup's formation as text, e.g. '4-4-2'."""
    players = list(players)
    if not players:
        return ''
    counts = Counter(position_of(p) for p in players)
    return f"{counts['DEF']}-{counts['MID']}-{counts['FWD']}"