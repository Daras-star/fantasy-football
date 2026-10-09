from django.db.models import F
from django.shortcuts import render
from django.utils import timezone

from .fixture_views import _default_gameweek
from .models import Fixture, Player

POSITION_SECTIONS = [
    ('GKP', 'Goalkeepers'),
    ('DEF', 'Defenders'),
    ('MID', 'Midfielders'),
    ('FWD', 'Forwards'),
]


def home(request):
    players = Player.objects.select_related('team', 'position')

    top_player = players.order_by('-total_points', 'web_name').first()

    news_players = list(
        players.exclude(status='a').exclude(news='').order_by('-total_points')[:8]
    )

    top_by_position = [
        (code, label, list(players.filter(position__short_name=code).order_by('-total_points')[:3]))
        for code, label in POSITION_SECTIONS
    ]

    gameweek = _default_gameweek()
    days = []
    if gameweek:
        matches = (
            Fixture.objects.filter(gameweek=gameweek)
            .select_related('home_team', 'away_team')
            .order_by(F('kickoff').asc(nulls_last=True), 'fpl_id')
        )
        for match in matches:
            day = timezone.localtime(match.kickoff).date() if match.kickoff else None
            if not days or days[-1]['date'] != day:
                days.append({'date': day, 'matches': []})
            days[-1]['matches'].append(match)

    return render(request, 'players/home.html', {
        'top_player': top_player,
        'news_players': news_players,
        'top_by_position': top_by_position,
        'gameweek': gameweek,
        'days': days,
    })