from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from players.models import Player, Team

from . import rules
from .chips import CHIPS
from .deadlines import next_gameweek, snapshot_missing, transfer_summary
from .live import live_gameweek, points_by_player
from .models import FantasyTeam, SquadPlayer
from .ranking import overall_rank
from .bank import get_bank
from .transfers import check_budget, selling_price

POSITION_ORDER = ['GKP', 'DEF', 'MID', 'FWD']
POSITION_LABELS = [(code, rules.POSITION_NAMES[code][0].title()) for code in POSITION_ORDER]


def _get_team(user):
    team, _ = FantasyTeam.objects.get_or_create(
        user=user,
        defaults={'name': f"{user.username}'s team"[:50]},
    )
    return team


def _to_int(value):
    return int(value) if value and value.isdigit() else None


def _open_for_edits(request):
    """Return the gameweek that changes count for, or None once the season is over."""
    target = next_gameweek()
    if target is None:
        messages.error(request, 'The season is over, so teams are locked.')
    return target
def _transfer_text(summary):
    if summary['first_squad']:
        return 'Your first squad is free to change until the next deadline.'
    if summary['chip']:
        return f"{summary['chip']} is active, so your changes cost nothing."
    word = 'transfer' if summary['made'] == 1 else 'transfers'
    text = f"{summary['made']} {word} made, {summary['free']} free."
    if summary['cost']:
        text += f" That costs {summary['cost']} points."
    return text
def _active_chip_name(team):
    target = next_gameweek()
    if target is None:
        return None
    play = team.chip_plays.filter(gameweek=target).first()
    return CHIPS[play.chip]['name'] if play else None
@login_required
def my_team(request):
    team = _get_team(request.user)
    snapshot_missing(team)
    squad = list(team.squad.select_related('player__team', 'player__position'))
    starters = [sp for sp in squad if sp.is_starter]
    bench = sorted(
        (sp for sp in squad if not sp.is_starter),
        key=lambda sp: POSITION_ORDER.index(rules.position_of(sp.player)),
    )
    pitch_rows = [
        (pos, [sp for sp in starters if rules.position_of(sp.player) == pos])
        for pos in POSITION_ORDER
    ]
    bank = get_bank(team)
    cost = sum(
        (selling_price(sp.bought_price, sp.player.price) for sp in squad), Decimal('0.0')
    )
    has_lineup = len(starters) == rules.STARTING_XI_SIZE

    # Points each player has earned in the gameweek being played (shown on the pitch)
    live = live_gameweek()
    live_points = points_by_player(live, squad) if live else {}
    for sp in squad:
        sp.gw_points = live_points.get(sp.player_id)

    return render(request, 'fantasy/my_team.html', {
        'live_gameweek': live,
        'live_counts': bool(live) and team.scores.filter(gameweek=live).exists(),
        'team': team,
        'pitch_rows': pitch_rows,
        'bench': bench,
        'cost': cost,
        'bank': bank,
        'has_squad': len(squad) == rules.SQUAD_SIZE,
        'has_lineup': has_lineup,
        'formation': rules.formation([sp.player for sp in starters]) if has_lineup else '',
        'next_gameweek': next_gameweek(),
        'rank': overall_rank(team),
        'active_chip': _active_chip_name(team),
        'transfers': transfer_summary(team),
    })


@login_required
def pick_squad(request):
    target = _open_for_edits(request)
    if target is None:
        return redirect('my_team')

    team = _get_team(request.user)
    snapshot_missing(team)
    bank = get_bank(team)
    current = {sp.player_id: sp for sp in team.squad.select_related('player')}
    errors = []
    team_name = team.name

    if request.method == 'POST':
        team_name = request.POST.get('team_name', '').strip()[:50] or team.name
        selected_ids = {int(i) for i in request.POST.getlist('players') if i.isdigit()}
        chosen = list(Player.objects.filter(pk__in=selected_ids).select_related('team', 'position'))

        if len(chosen) != len(selected_ids):
            errors.append('Some of the players you picked could not be found.')
        errors += rules.validate_squad(chosen, check_budget=False)

        sold_values = [
            selling_price(sp.bought_price, sp.player.price)
            for player_id, sp in current.items() if player_id not in selected_ids
        ]
        bought_prices = [p.price for p in chosen if p.pk not in current]
        new_bank, money_errors = check_budget(bank, sold_values, bought_prices)
        errors += money_errors

        if not errors:
            with transaction.atomic():
                snapshot_missing(team)  # freeze closed gameweeks BEFORE the team changes
                team.name = team_name
                team.bank = new_bank
                team.save(update_fields=['name', 'bank'])
                team.squad.exclude(player_id__in=selected_ids).delete()
                already_in = set(team.squad.values_list('player_id', flat=True))
                SquadPlayer.objects.bulk_create(
                    SquadPlayer(fantasy_team=team, player=p, bought_price=p.price)
                    for p in chosen if p.pk not in already_in
                )
            messages.success(
                request,
                f'Squad saved. It counts from {target.name}. '
                f'{_transfer_text(transfer_summary(team))} Now choose your starting XI.',
            )
            return redirect('pick_lineup')
    else:
        selected_ids = set(current)

    funds = bank + sum(
        (selling_price(sp.bought_price, sp.player.price) for sp in current.values()),
        Decimal('0.0'),
    )

    return render(request, 'fantasy/pick_squad.html', {
        'players': Player.objects.select_related('team', 'position'),
        'teams': Team.objects.all(),
        'positions': POSITION_LABELS,
        'position_limits': [
            (code, label, rules.POSITION_LIMITS[code]) for code, label in POSITION_LABELS
        ],
        'selected_ids': selected_ids,
        'team_name': team_name,
        'errors': errors,
        'budget': funds,
        'bank': bank,
        'squad_size': rules.SQUAD_SIZE,
        'transfers': transfer_summary(team),
    })


@login_required
def pick_lineup(request):
    target = _open_for_edits(request)
    if target is None:
        return redirect('my_team')

    team = _get_team(request.user)
    squad = list(team.squad.select_related('player__team', 'player__position'))

    if len(squad) != rules.SQUAD_SIZE:
        messages.info(request, f'Pick your {rules.SQUAD_SIZE}-player squad first.')
        return redirect('pick_squad')

    squad.sort(
        key=lambda sp: (POSITION_ORDER.index(rules.position_of(sp.player)), -sp.player.total_points)
    )
    squad_ids = {sp.player_id for sp in squad}
    errors = []

    if request.method == 'POST':
        selected_ids = {int(i) for i in request.POST.getlist('starters') if i.isdigit()}
        captain_id = _to_int(request.POST.get('captain'))
        vice_id = _to_int(request.POST.get('vice_captain'))

        if not selected_ids <= squad_ids:
            errors.append('You can only start players from your own squad.')
        starters = [sp.player for sp in squad if sp.player_id in selected_ids]
        errors += rules.validate_starting_xi(starters)
        errors += rules.validate_captains(captain_id, vice_id, selected_ids)

        if not errors:
            with transaction.atomic():
                snapshot_missing(team)  # freeze closed gameweeks BEFORE the lineup changes
                for sp in squad:
                    sp.is_starter = sp.player_id in selected_ids
                    sp.is_captain = sp.player_id == captain_id
                    sp.is_vice_captain = sp.player_id == vice_id
                    sp.save(update_fields=['is_starter', 'is_captain', 'is_vice_captain'])
            messages.success(request, f'Lineup saved. It counts from {target.name}.')
            return redirect('my_team')
    else:
        selected_ids = {sp.player_id for sp in squad if sp.is_starter}
        captain_id = next((sp.player_id for sp in squad if sp.is_captain), None)
        vice_id = next((sp.player_id for sp in squad if sp.is_vice_captain), None)

    return render(request, 'fantasy/pick_lineup.html', {
        'squad': squad,
        'selected_ids': selected_ids,
        'captain_id': captain_id,
        'vice_id': vice_id,
        'errors': errors,
    })