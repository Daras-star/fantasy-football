from django.db.models import F
from django.shortcuts import render

from .models import Fixture, Gameweek, Team
from .standings import build_table

VENUES = ('all', 'home', 'away')
TOP_PLACES = 4
BOTTOM_PLACES = 3


def league_table(request):
    venue = request.GET.get('venue', 'all')
    if venue not in VENUES:
        venue = 'all'

    gameweeks = list(
        Gameweek.objects.filter(fixtures__finished=True).distinct().order_by('number')
    )
    selected = None
    number = request.GET.get('gw', '')
    if number.isdigit():
        selected = next((g for g in gameweeks if g.number == int(number)), None)

    teams = {team.id: team for team in Team.objects.all()}

    played = Fixture.objects.filter(
        finished=True, home_score__isnull=False, away_score__isnull=False
    )
    if selected:
        played = played.filter(gameweek__number__lte=selected.number)
    results = [
        (f.home_team_id, f.away_team_id, f.home_score, f.away_score)
        for f in played.order_by('kickoff', 'fpl_id')
    ]

    table = build_table({team_id: team.name for team_id, team in teams.items()}, results, venue)

    # Each club's next match: the first one still to come (or after the chosen gameweek)
    later = Fixture.objects.select_related('home_team', 'away_team')
    if selected:
        later = later.filter(gameweek__number__gt=selected.number)
    else:
        later = later.filter(finished=False)
    next_for = {}
    for fixture in later.order_by(F('kickoff').asc(nulls_last=True), 'fpl_id'):
        next_for.setdefault(fixture.home_team_id, (fixture.away_team, 'H'))
        next_for.setdefault(fixture.away_team_id, (fixture.home_team, 'A'))

    for row in table:
        row['team'] = teams[row['team_id']]
        row['next'] = next_for.get(row['team_id'])
        if row['position'] <= TOP_PLACES:
            row['zone'] = 'top'
        elif row['position'] > len(table) - BOTTOM_PLACES:
            row['zone'] = 'bottom'
        else:
            row['zone'] = ''

    return render(request, 'players/table.html', {
        'table': table,
        'gameweeks': gameweeks,
        'selected': selected,
        'venue': venue,
        'has_results': bool(results),
    })