from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Fixture, Player, Position, Team

# Sort choices for the player list: key -> (label, database ordering)
SORT_OPTIONS = {
    "points": ("Points", "-total_points"),
    "price": ("Price", "-price"),
    "name": ("Name", "web_name"),
}


def player_list(request):
    players = Player.objects.select_related("team", "position")

    position = request.GET.get("position", "")
    team = request.GET.get("team", "")
    search = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "points")
    if sort not in SORT_OPTIONS:
        sort = "points"

    if position:
        players = players.filter(position__short_name=position)
    if team:
        players = players.filter(team__short_name=team)
    if search:
        players = players.filter(
            Q(web_name__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )
    players = players.order_by(SORT_OPTIONS[sort][1], "web_name")

    page_obj = Paginator(players, 25).get_page(request.GET.get("page"))

    # Page links keep the current filters but drop the old page number.
    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "positions": Position.objects.all(),
        "teams": Team.objects.all(),
        "sort_options": [(key, label) for key, (label, _) in SORT_OPTIONS.items()],
        "selected": {"position": position, "team": team, "q": search, "sort": sort},
        "querystring": params.urlencode(),
    }
    return render(request, "players/player_list.html", context)


def player_detail(request, pk):
    player = get_object_or_404(Player.objects.select_related("team", "position"), pk=pk)

    fixtures = (
        Fixture.objects.filter(
            Q(home_team=player.team) | Q(away_team=player.team),
            finished=False,
            kickoff__isnull=False,
        )
        .select_related("home_team", "away_team", "gameweek")
        .order_by("kickoff")[:5]
    )

    upcoming = []
    for fixture in fixtures:
        at_home = fixture.home_team_id == player.team_id
        upcoming.append(
            {
                "fixture": fixture,
                "opponent": fixture.away_team if at_home else fixture.home_team,
                "venue": "Home" if at_home else "Away",
            }
        )

    return render(request, "players/player_detail.html", {"player": player, "upcoming": upcoming})