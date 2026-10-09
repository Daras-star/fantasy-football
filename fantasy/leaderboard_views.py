from django.core.paginator import Paginator
from django.shortcuts import render

from players.models import Gameweek

from .models import GameweekScore
from .ranking import assign_ranks, full_squad_teams

PAGE_SIZE = 50


def leaderboard(request):
    gameweeks = list(
        Gameweek.objects.filter(team_scores__isnull=False).distinct().order_by('number')
    )

    selected = None
    number = request.GET.get('gw', '')
    if number.isdigit():
        selected = next((g for g in gameweeks if g.number == int(number)), None)

    if selected:
        scores = (
            GameweekScore.objects.filter(gameweek=selected)
            .select_related('fantasy_team__user')
            .order_by('-points', 'fantasy_team__name')
        )
        entries = [(score.fantasy_team, score.points) for score in scores]
    else:
        teams = full_squad_teams().select_related('user').order_by('-total_points', 'name')
        entries = [(team, team.total_points) for team in teams]

    ranked = assign_ranks(entries)

    mine = None
    if request.user.is_authenticated:
        mine = next((row for row in ranked if row['item'].user_id == request.user.id), None)

    page = Paginator(ranked, PAGE_SIZE).get_page(request.GET.get('page'))

    # On the overall table, also show points from the latest scored gameweek
    latest = gameweeks[-1] if gameweeks else None
    if latest and not selected:
        latest_points = dict(
            GameweekScore.objects.filter(gameweek=latest).values_list('fantasy_team_id', 'points')
        )
        for row in page:
            row['gw_points'] = latest_points.get(row['item'].pk)

    return render(request, 'fantasy/leaderboard.html', {
        'page': page,
        'selected': selected,
        'gameweeks': gameweeks,
        'latest': latest,
        'mine': mine,
        'total': len(ranked),
    })