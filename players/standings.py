"""League table calculation. Plain Python (no database)."""

WIN_POINTS = 3
DRAW_POINTS = 1
FORM_LENGTH = 5


def build_table(teams, results, venue='all'):
    """Work out the league table.

    teams: {team_id: name}, so clubs with no matches still appear
    results: finished matches as (home_id, away_id, home_goals, away_goals),
             oldest first (the order decides the form guide)
    venue: 'all', 'home' (count only home games) or 'away'

    Returns a list of row dicts, best team first, each with a 'position'.
    Ties are broken by goal difference, then goals scored, then name.
    """
    rows = {
        team_id: {
            'team_id': team_id,
            'name': name,
            'played': 0,
            'won': 0,
            'drawn': 0,
            'lost': 0,
            'goals_for': 0,
            'goals_against': 0,
            'form': [],
        }
        for team_id, name in teams.items()
    }

    def record(team_id, scored, conceded):
        row = rows.get(team_id)
        if row is None:
            return
        row['played'] += 1
        row['goals_for'] += scored
        row['goals_against'] += conceded
        if scored > conceded:
            row['won'] += 1
            row['form'].append('W')
        elif scored == conceded:
            row['drawn'] += 1
            row['form'].append('D')
        else:
            row['lost'] += 1
            row['form'].append('L')

    for home_id, away_id, home_goals, away_goals in results:
        if venue in ('all', 'home'):
            record(home_id, home_goals, away_goals)
        if venue in ('all', 'away'):
            record(away_id, away_goals, home_goals)

    table = []
    for row in rows.values():
        row['goal_difference'] = row['goals_for'] - row['goals_against']
        row['points'] = WIN_POINTS * row['won'] + DRAW_POINTS * row['drawn']
        row['form'] = row['form'][-FORM_LENGTH:]
        table.append(row)

    table.sort(
        key=lambda r: (-r['points'], -r['goal_difference'], -r['goals_for'], r['name'].lower())
    )
    for position, row in enumerate(table, start=1):
        row['position'] = position
    return table