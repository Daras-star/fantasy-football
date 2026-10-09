"""Gameweek deadlines: which gameweek changes count for, and freezing lineups."""
from django.db import transaction
from django.utils import timezone

from players.models import Gameweek

from .chips import CHIPS, FREE_HIT, UNLIMITED_TRANSFER_CHIPS
from .models import GameweekPick, GameweekScore, SquadPlayer
from .transfers import next_free_transfers, transfer_cost, transfers_made


def next_gameweek():
    """The gameweek your changes count for: the first one whose deadline is still ahead."""
    return Gameweek.objects.filter(deadline__gt=timezone.now()).order_by('number').first()


def passed_gameweeks():
    """Every gameweek whose deadline has gone, oldest first."""
    return Gameweek.objects.filter(deadline__lte=timezone.now()).order_by('number')


def last_frozen_score(team, before_number=None):
    """The team's most recent frozen lineup, ignoring Free Hit gameweeks.

    A Free Hit squad only lasts one gameweek, so it is never the starting
    point for counting later transfers.
    """
    free_hit_ids = set(
        team.chip_plays.filter(chip=FREE_HIT).values_list('gameweek_id', flat=True)
    )
    scores = team.scores.exclude(gameweek_id__in=free_hit_ids)
    if before_number is not None:
        scores = scores.filter(gameweek__number__lt=before_number)
    return scores.order_by('-gameweek__number').first()


def last_frozen_player_ids(team, before_number=None):
    """Player ids in the team's last frozen lineup (empty set if there is none)."""
    score = last_frozen_score(team, before_number)
    if score is None:
        return set()
    return set(score.picks.values_list('player_id', flat=True))


@transaction.atomic
def restore_squad(team, score):
    """Put the team's current squad back to a frozen lineup."""
    picks = list(score.picks.all())
    team.squad.all().delete()
    SquadPlayer.objects.bulk_create(
        SquadPlayer(
            fantasy_team=team,
            player_id=pick.player_id,
            is_starter=pick.is_starter,
            is_captain=pick.is_captain,
            is_vice_captain=pick.is_vice_captain,
            bought_price=pick.bought_price,
        )
        for pick in picks
    )
    team.bank = score.bank
    team.save(update_fields=['bank'])


def transfer_summary(team):
    """Transfers made since the last deadline, what they cost, and the free ones available."""
    target = next_gameweek()
    chip = None
    if target is not None:
        play = team.chip_plays.filter(
            gameweek=target, chip__in=UNLIMITED_TRANSFER_CHIPS
        ).first()
        chip = CHIPS[play.chip]['name'] if play else None

    baseline = last_frozen_player_ids(team)
    if not baseline:
        # No lineup has been frozen yet, so building the first squad is free
        return {'first_squad': True, 'made': 0, 'free': team.free_transfers, 'cost': 0, 'chip': chip}

    current = set(team.squad.values_list('player_id', flat=True))
    made = transfers_made(baseline, current)
    return {
        'first_squad': False,
        'made': made,
        'free': team.free_transfers,
        'cost': 0 if chip else transfer_cost(made, team.free_transfers),
        'chip': chip,
    }


@transaction.atomic
def snapshot_missing(team, include_before_joining=False):
    """Freeze the team's lineup for every gameweek whose deadline has passed.

    A frozen lineup is a GameweekScore plus one GameweekPick per squad player.
    Transfers are counted against the previous frozen lineup: extra ones are
    stored as the score's transfer_cost, and the team's free transfers are updated.
    A Wildcard or Free Hit makes the gameweek's transfers free. After a Free Hit
    gameweek is frozen, the squad goes back to the lineup from before it.
    Gameweeks that closed before the team existed are skipped, unless
    include_before_joining is True (used for testing with old data).
    Returns how many gameweeks were frozen.
    """
    already = set(team.scores.values_list('gameweek_id', flat=True))
    chip_by_gameweek = dict(team.chip_plays.values_list('gameweek_id', 'chip'))
    squad = list(team.squad.all())
    current_ids = {entry.player_id for entry in squad}
    frozen = 0

    for gameweek in passed_gameweeks():
        if gameweek.id in already:
            continue
        if not include_before_joining and gameweek.deadline < team.created_at:
            continue

        chip = chip_by_gameweek.get(gameweek.id)
        previous = last_frozen_score(team, before_number=gameweek.number)

        if previous is not None:
            previous_ids = set(previous.picks.values_list('player_id', flat=True))
            made = transfers_made(previous_ids, current_ids)
            if chip in UNLIMITED_TRANSFER_CHIPS:
                cost, counted = 0, 0
            else:
                cost, counted = transfer_cost(made, team.free_transfers), made
            team.free_transfers = next_free_transfers(team.free_transfers, counted)
        else:
            cost = 0

        score = GameweekScore.objects.create(
            fantasy_team=team, gameweek=gameweek, points=0, transfer_cost=cost, bank=team.bank
        )
        GameweekPick.objects.bulk_create(
            GameweekPick(
                score=score,
                player_id=entry.player_id,
                is_starter=entry.is_starter,
                is_captain=entry.is_captain,
                is_vice_captain=entry.is_vice_captain,
                bought_price=entry.bought_price,
            )
            for entry in squad
        )
        frozen += 1

        if chip == FREE_HIT and previous is not None:
            restore_squad(team, previous)
            squad = list(team.squad.all())
            current_ids = {entry.player_id for entry in squad}

    if frozen:
        team.save(update_fields=['free_transfers'])

    return frozen