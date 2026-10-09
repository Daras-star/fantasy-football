"""Chips: special one-gameweek powers. Plain Python (no database)."""

# Each chip can be used once in each of these halves of the season
CHIP_WINDOWS = [(1, 19), (20, 38)]

WILDCARD = 'WC'
FREE_HIT = 'FH'

CHIPS = {
    'WC': {
        'name': 'Wildcard',
        'description': 'Make unlimited transfers with no points cost. The new squad is permanent.',
    },
    'FH': {
        'name': 'Free Hit',
        'description': 'Make unlimited transfers for one gameweek only. Your squad then goes back to how it was.',
    },
    'TC': {
        'name': 'Triple Captain',
        'description': 'Your captain scores triple points instead of double.',
    },
    'BB': {
        'name': 'Bench Boost',
        'description': 'Points from your bench players count as well as your starting XI.',
    },
}

# Chips that make transfers free for the gameweek they are played
UNLIMITED_TRANSFER_CHIPS = (WILDCARD, FREE_HIT)

# The first gameweek each chip can be played (chips not listed can be played from 1)
FIRST_GAMEWEEK = {'WC': 2, 'FH': 2}


def window_of(gameweek_number):
    """Which half of the season a gameweek is in (0 or 1), or None."""
    for index, (first, last) in enumerate(CHIP_WINDOWS):
        if first <= gameweek_number <= last:
            return index
    return None


def chip_states(plays, target_number):
    """What each chip can do for the target gameweek.

    plays: list of (chip_code, gameweek_number) the team has already activated.
    Returns {chip_code: {'state': ..., 'used_in': gameweek number or None}}

    States:
      active     on for the target gameweek
      blocked    another chip is already active this gameweek
      used       already used earlier in this half of the season
      early      too early in the season for this chip
      cooldown   Free Hit cannot be played two gameweeks in a row
      available  can be played
    """
    active = next((chip for chip, number in plays if number == target_number), None)
    target_window = window_of(target_number)

    states = {}
    for code in CHIPS:
        used_in = next(
            (
                number
                for chip, number in plays
                if chip == code and number != target_number and window_of(number) == target_window
            ),
            None,
        )
        played_last_week = code == FREE_HIT and any(
            chip == FREE_HIT and number == target_number - 1 for chip, number in plays
        )
        if active == code:
            state = 'active'
        elif active is not None:
            state = 'blocked'
        elif used_in is not None:
            state = 'used'
        elif target_number < FIRST_GAMEWEEK.get(code, 1):
            state = 'early'
        elif played_last_week:
            state = 'cooldown'
        else:
            state = 'available'
        states[code] = {'state': state, 'used_in': used_in}
    return states