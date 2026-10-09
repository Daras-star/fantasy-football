"""A team's money in the bank."""
from decimal import Decimal

from . import rules
from .models import SquadPlayer


def get_bank(team):
    """Money in the bank. Older teams get it worked out the first time it is needed."""
    if team.bank is None:
        squad = list(team.squad.select_related('player'))
        spent = sum((sp.player.price for sp in squad), Decimal('0.0'))
        team.bank = max(Decimal('0.0'), rules.BUDGET - spent)
        team.save(update_fields=['bank'])

        missing = [sp for sp in squad if sp.bought_price is None]
        for sp in missing:
            sp.bought_price = sp.player.price
        SquadPlayer.objects.bulk_update(missing, ['bought_price'])
    return team.bank