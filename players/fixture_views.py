from django.db.models import F
from django.shortcuts import render
from django.utils import timezone

from .models import Fixture, Gameweek


def _default_gameweek():
    """The first gameweek that hasn't finished, or the latest one at season end."""
    return (
        Gameweek.objects.filter(finished=False).order_by('number').first()
        or Gameweek.objects.order_by('-number').first()
    )


def fixtures(request):
    gameweek = None
    number = request.GET.get('gw', '')
    if number.isdigit():
        gameweek = Gameweek.objects.filter(number=int(number)).first()
    if gameweek is None:
        gameweek = _default_gameweek()

    if gameweek is None:
        return render(request, 'players/fixtures.html', {'gameweek': None})

    matches = list(
        Fixture.objects.filter(gameweek=gameweek)
        .select_related('home_team', 'away_team')
        .order_by(F('kickoff').asc(nulls_last=True), 'fpl_id')
    )

    # Group the matches by calendar day
    days = []
    for match in matches:
        day = timezone.localtime(match.kickoff).date() if match.kickoff else None
        if not days or days[-1]['date'] != day:
            days.append({'date': day, 'matches': []})
        days[-1]['matches'].append(match)

    dated = [d['date'] for d in days if d['date']]

    return render(request, 'players/fixtures.html', {
        'gameweek': gameweek,
        'days': days,
        'start': dated[0] if dated else None,
        'end': dated[-1] if dated else None,
        'previous': Gameweek.objects.filter(number__lt=gameweek.number).order_by('-number').first(),
        'following': Gameweek.objects.filter(number__gt=gameweek.number).order_by('number').first(),
    })