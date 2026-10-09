from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import rules
from .chips import CHIPS, FREE_HIT, chip_states
from .deadlines import last_frozen_score, next_gameweek, restore_squad, snapshot_missing
from .models import ChipPlay
from .views import _get_team


def _plays(team):
    return [
        (play.chip, play.gameweek.number)
        for play in team.chip_plays.select_related('gameweek')
    ]


def _has_full_lineup(team):
    squad = list(team.squad.all())
    starters = [entry for entry in squad if entry.is_starter]
    return len(squad) == rules.SQUAD_SIZE and len(starters) == rules.STARTING_XI_SIZE


@login_required
def chip_list(request):
    team = _get_team(request.user)
    target = next_gameweek()

    states = chip_states(_plays(team), target.number) if target else {}
    cards = []
    for code, info in CHIPS.items():
        state = states.get(code, {'state': 'season_over', 'used_in': None})
        cards.append({
            'code': code,
            'name': info['name'],
            'description': info['description'],
            **state,
        })

    history = [
        {'chip': CHIPS[play.chip]['name'], 'gameweek': play.gameweek}
        for play in team.chip_plays.select_related('gameweek')
        if play.chip in CHIPS
    ]

    return render(request, 'fantasy/chips.html', {
        'cards': cards,
        'target': target,
        'ready': _has_full_lineup(team),
        'history': history,
    })


@login_required
@require_POST
def play_chip(request):
    team = _get_team(request.user)
    snapshot_missing(team)  # freeze closed gameweeks before anything changes
    target = next_gameweek()
    code = request.POST.get('chip', '')

    if target is None:
        messages.error(request, 'The season is over, so chips are locked.')
    elif code not in CHIPS:
        messages.error(request, 'That chip does not exist.')
    elif not _has_full_lineup(team):
        messages.error(request, 'Pick your squad and starting XI before playing a chip.')
    else:
        state = chip_states(_plays(team), target.number)[code]['state']
        name = CHIPS[code]['name']
        if state == 'available':
            try:
                with transaction.atomic():
                    ChipPlay.objects.create(fantasy_team=team, gameweek=target, chip=code)
            except IntegrityError:
                messages.error(request, 'You already have a chip active this gameweek.')
            else:
                messages.success(request, f'{name} is active for {target.name}.')
        elif state == 'active':
            messages.info(request, f'{name} is already active for {target.name}.')
        elif state == 'blocked':
            messages.error(
                request, 'Only one chip can be played per gameweek. Cancel your active chip first.'
            )
        elif state == 'early':
            messages.error(request, f'{name} cannot be played in {target.name}. It opens from Gameweek 2.')
        elif state == 'cooldown':
            messages.error(request, f'{name} cannot be played two gameweeks in a row.')
        else:
            messages.error(request, f'You have already used {name} in this half of the season.')

    return redirect('chips')


@login_required
@require_POST
def cancel_chip(request):
    team = _get_team(request.user)
    snapshot_missing(team)
    target = next_gameweek()

    if target is None:
        messages.error(request, 'The season is over, so chips are locked.')
        return redirect('chips')

    play = ChipPlay.objects.filter(fantasy_team=team, gameweek=target).first()
    if play is None:
        messages.info(request, 'You have no chip active to cancel.')
        return redirect('chips')

    code = play.chip
    play.delete()

    if code == FREE_HIT:
        baseline = last_frozen_score(team)
        if baseline is not None:
            restore_squad(team, baseline)
            messages.success(
                request,
                f'Free Hit cancelled for {target.name}. Your squad is back to how it was '
                'at the last deadline.',
            )
        else:
            messages.success(request, f'Free Hit cancelled for {target.name}.')
    else:
        messages.success(request, f'Chip cancelled for {target.name}.')

    return redirect('chips')