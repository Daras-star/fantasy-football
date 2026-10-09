"""Gameweek scoring: turns match stats into points for every fantasy team."""
from collections import defaultdict

from django.db import transaction
from django.db.models import Sum

from players.models import PlayerFixtureStats

from .models import ChipPlay, FantasyTeam, GameweekScore
from .scoring import calculate_team_points


def stats_for_gameweek(gameweek):
    """Return {player_id: [match stats, ...]} for every match in the gameweek.

    A player has two rows in a double gameweek.
    """
    by_player = defaultdict(list)
    for row in PlayerFixtureStats.objects.filter(fixture__gameweek=gameweek):
        by_player[row.player_id].append(row)
    return by_player


def update_gameweek_scores(gameweek):
    """Score every frozen lineup for the gameweek. Returns how many were scored."""
    stats = stats_for_gameweek(gameweek)
    chips = dict(
        ChipPlay.objects.filter(gameweek=gameweek).values_list('fantasy_team_id', 'chip')
    )
    scores = list(
        GameweekScore.objects.filter(gameweek=gameweek)
        .prefetch_related('picks__player__position')
    )

    with transaction.atomic():
        for score in scores:
            points = calculate_team_points(
                list(score.picks.all()), stats, chip=chips.get(score.fantasy_team_id)
            ) - score.transfer_cost
            
            if score.points != points:
                score.points = points
                score.save(update_fields=['points'])

    return len(scores)


def refresh_totals():
    """Set each team's total_points to the sum of its gameweek scores."""
    for team in FantasyTeam.objects.annotate(total=Sum('scores__points')):
        total = team.total or 0
        if team.total_points != total:
            team.total_points = total
            team.save(update_fields=['total_points'])