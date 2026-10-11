from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import rules
from .chips import CHIPS
from .deadlines import next_gameweek, passed_gameweeks, snapshot_missing
from .models import ChipPlay
from .scoring import team_breakdown
from .tasks import stats_for_gameweek
from .views import POSITION_ORDER, _get_team


@login_required
def gameweek_points(request):
    team = _get_team(request.user)

    # Lock in the lineup for any deadline that has passed. If you haven't changed
    # your team since the deadline, your current lineup is the one that played.
    snapshot_missing(team)

    scores = list(team.scores.select_related('gameweek').order_by('gameweek__number'))
    selected = None
    number = request.GET.get('gw', '')
    if number.isdigit():
        selected = next((s for s in scores if s.gameweek.number == int(number)), None)
    if selected is None and scores:
        selected = scores[-1]

    context = {
        'team': team,
        'scores': scores,
        'selected': selected,
        'next_gameweek': next_gameweek(),
    }

    if selected is None:
        last_closed = passed_gameweeks().last()
        context['last_closed'] = last_closed
        context['joined_late'] = bool(last_closed and last_closed.deadline < team.created_at)
        return render(request, 'fantasy/points.html', context)

    gameweek = selected.gameweek
    picks = list(selected.picks.select_related('player__team', 'player__position'))
    chip_play = ChipPlay.objects.filter(fantasy_team=team, gameweek=gameweek).first()
    chip = chip_play.chip if chip_play else None

    rows = team_breakdown(picks, stats_for_gameweek(gameweek), chip=chip)
    for row in rows:
        row['display'] = row['points'] if row['counts'] else row['base']

    pitch_rows = [
        (pos, [
            r for r in rows
            if r['entry'].is_starter and rules.position_of(r['entry'].player) == pos
        ])
        for pos in POSITION_ORDER
    ]
    bench = sorted(
        (r for r in rows if not r['entry'].is_starter),
        key=lambda r: POSITION_ORDER.index(rules.position_of(r['entry'].player)),
    )

    gross = sum(r['points'] for r in rows)
    transfer_cost = getattr(selected, 'transfer_cost', 0) or 0
    context.update({
        'pitch_rows': pitch_rows,
        'bench': bench,
        'gross': gross,
        'transfer_cost': transfer_cost,
        'net': gross - transfer_cost,
        'chip_name': CHIPS.get(chip, {}).get('name'),
    })
    return render(request, 'fantasy/points.html', context)