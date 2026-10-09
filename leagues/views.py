from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from fantasy.models import FantasyTeam, GameweekScore
from fantasy.ranking import assign_ranks
from players.models import Gameweek

from .models import League, LeagueMember


def _my_team(user):
    team, _ = FantasyTeam.objects.get_or_create(
        user=user,
        defaults={'name': f"{user.username}'s team"[:50]},
    )
    return team


def _standings(league, gameweek=None):
    """Ranked rows for a league: overall, or for one gameweek."""
    members = list(league.members.select_related('team__user'))
    if gameweek:
        points = dict(
            GameweekScore.objects.filter(
                gameweek=gameweek, fantasy_team_id__in=[m.team_id for m in members]
            ).values_list('fantasy_team_id', 'points')
        )
        entries = [(m.team, points.get(m.team_id, 0)) for m in members]
    else:
        entries = [(m.team, m.team.total_points) for m in members]
    entries.sort(key=lambda item: (-item[1], item[0].name.lower()))
    return assign_ranks(entries)


@login_required
def league_list(request):
    team = _my_team(request.user)
    memberships = (
        LeagueMember.objects.filter(team=team).select_related('league').order_by('league__name')
    )

    rows = []
    for membership in memberships:
        league = membership.league
        standings = _standings(league)
        mine = next((row for row in standings if row['item'].pk == team.pk), None)
        rows.append({
            'league': league,
            'members': len(standings),
            'rank': mine['rank'] if mine else None,
            'is_admin': league.admin_id == request.user.id,
        })

    return render(request, 'leagues/league_list.html', {'rows': rows})


@login_required
@require_POST
def create_league(request):
    name = request.POST.get('name', '').strip()[:50]
    if not name:
        messages.error(request, 'Give your league a name.')
        return redirect('leagues:list')

    team = _my_team(request.user)
    with transaction.atomic():
        league = League.objects.create(name=name, admin=request.user)
        LeagueMember.objects.create(league=league, team=team)

    messages.success(
        request, f'League created. Share the code {league.join_code} with your friends.'
    )
    return redirect('leagues:detail', pk=league.pk)


@login_required
@require_POST
def join_league(request):
    code = request.POST.get('code', '').strip().upper()
    league = League.objects.filter(join_code=code).first() if code else None
    if league is None:
        messages.error(request, "That code doesn't match any league. Check it and try again.")
        return redirect('leagues:list')

    team = _my_team(request.user)
    _, created = LeagueMember.objects.get_or_create(league=league, team=team)
    if created:
        messages.success(request, f'You joined {league.name}.')
    else:
        messages.info(request, f'You are already in {league.name}.')
    return redirect('leagues:detail', pk=league.pk)


@login_required
def league_detail(request, pk):
    team = _my_team(request.user)
    league = get_object_or_404(League, pk=pk, members__team=team)  # members only

    gameweeks = list(
        Gameweek.objects.filter(team_scores__isnull=False).distinct().order_by('number')
    )
    selected = None
    number = request.GET.get('gw', '')
    if number.isdigit():
        selected = next((g for g in gameweeks if g.number == int(number)), None)

    standings = _standings(league, selected)
    mine = next((row for row in standings if row['item'].pk == team.pk), None)

    return render(request, 'leagues/league_detail.html', {
        'league': league,
        'standings': standings,
        'gameweeks': gameweeks,
        'selected': selected,
        'mine': mine,
        'is_admin': league.admin_id == request.user.id,
    })


@login_required
@require_POST
def leave_league(request, pk):
    team = _my_team(request.user)
    membership = get_object_or_404(LeagueMember, league_id=pk, team=team)

    if membership.league.admin_id == request.user.id:
        messages.error(
            request, 'You created this league, so you cannot leave it. You can delete it instead.'
        )
        return redirect('leagues:detail', pk=pk)

    name = membership.league.name
    membership.delete()
    messages.success(request, f'You left {name}.')
    return redirect('leagues:list')


@login_required
@require_POST
def delete_league(request, pk):
    league = get_object_or_404(League, pk=pk)
    if league.admin_id != request.user.id:
        messages.error(request, 'Only the person who created a league can delete it.')
        return redirect('leagues:list')

    name = league.name
    league.delete()
    messages.success(request, f'{name} was deleted.')
    return redirect('leagues:list')