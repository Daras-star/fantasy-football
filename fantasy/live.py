"""Points for the gameweek that is being played, shown on the My team pitch."""
from collections import defaultdict

from players.models import Gameweek, PlayerFixtureStats

from .rules import position_of
from .scoring import calculate_gameweek_points


def live_gameweek():
    """The current gameweek once it has match stats, otherwise the latest one that has any."""
    current = Gameweek.objects.filter(is_current=True).first()
    if current is not None and PlayerFixtureStats.objects.filter(fixture__gameweek=current).exists():
        return current
    return (
        Gameweek.objects.filter(fixtures__player_stats__isnull=False)
        .distinct()
        .order_by('-number')
        .first()
    )


def points_by_player(gameweek, entries):
    """Return {player_id: points} for every player in `entries` who has played."""
    entries = list(entries)
    matches = defaultdict(list)
    rows = PlayerFixtureStats.objects.filter(
        fixture__gameweek=gameweek,
        player_id__in=[entry.player_id for entry in entries],
    )
    for row in rows:
        matches[row.player_id].append(row)

    return {
        entry.player_id: calculate_gameweek_points(position_of(entry.player), matches[entry.player_id])
        for entry in entries
        if entry.player_id in matches
    }