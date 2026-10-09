"""Automatic substitutions: bench players replace starters who didn't play. Plain Python."""
from collections import Counter

from .rules import FORMATION_LIMITS, position_of

# Bench order until managers can choose their own: goalkeeper first, then outfielders
BENCH_ORDER = ['GKP', 'DEF', 'MID', 'FWD']


def _formation_valid(entries):
    counts = Counter(position_of(e.player) for e in entries)
    return all(
        low <= counts.get(position, 0) <= high
        for position, (low, high) in FORMATION_LIMITS.items()
    )


def auto_substitutions(squad, played):
    """Work out who really scores after automatic substitutions.

    squad: SquadPlayer or GameweekPick objects for the team.
    played: function that takes an entry and says whether the player played.
    Returns (lineup, swaps): the 11 entries that count, and a list of
    (player_out, player_in) pairs.
    """
    lineup = [e for e in squad if e.is_starter]
    bench = sorted(
        (e for e in squad if not e.is_starter),
        key=lambda e: BENCH_ORDER.index(position_of(e.player)),
    )
    swaps = []

    for sub in bench:
        if not played(sub):
            continue
        for starter in lineup:
            if played(starter):
                continue
            candidate = [sub if e is starter else e for e in lineup]
            if _formation_valid(candidate):
                lineup = candidate
                swaps.append((starter, sub))
                break

    return lineup, swaps