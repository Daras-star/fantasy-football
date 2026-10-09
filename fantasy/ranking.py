"""Leaderboard helpers: ranking with ties, and a team's overall rank."""
from django.db.models import Count

from . import rules
from .models import FantasyTeam


def full_squad_teams():
    """Teams that have picked a complete squad. Only these appear on the leaderboard."""
    return FantasyTeam.objects.annotate(squad_size=Count('squad')).filter(
        squad_size=rules.SQUAD_SIZE
    )


def assign_ranks(entries):
    """entries: a list of (item, points), best first.

    Equal points share a rank, so the ranks run 1, 2, 2, 4.
    """
    ranked = []
    previous = None
    rank = 0
    for position, (item, points) in enumerate(entries, start=1):
        if points != previous:
            rank = position
            previous = points
        ranked.append({'rank': rank, 'item': item, 'points': points})
    return ranked


def overall_rank(team):
    """Return (rank, number_of_teams) for a team, or None if it has no full squad."""
    teams = full_squad_teams()
    if not teams.filter(pk=team.pk).exists():
        return None
    ahead = teams.filter(total_points__gt=team.total_points).count()
    return ahead + 1, teams.count()