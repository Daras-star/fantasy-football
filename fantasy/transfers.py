"""Transfers: free-transfer bank, point hits and selling prices. Plain Python."""
from decimal import ROUND_FLOOR, Decimal

FREE_TRANSFERS_PER_GAMEWEEK = 1
MAX_BANKED_FREE_TRANSFERS = 5
HIT_COST = 4


def transfers_made(previous_ids, current_ids):
    """How many players were swapped out since the last deadline."""
    return len(set(previous_ids) - set(current_ids))


def transfer_cost(made, free_transfers):
    """Points deducted: every transfer beyond the free ones costs HIT_COST."""
    return max(0, made - free_transfers) * HIT_COST


def next_free_transfers(free_before, made):
    """Free transfers a team has for the next gameweek, after this one locks."""
    remaining = max(0, free_before - made)
    return min(MAX_BANKED_FREE_TRANSFERS, remaining + FREE_TRANSFERS_PER_GAMEWEEK)


def selling_price(buy_price, current_price):
    """You keep half of any price rise, rounded down to 0.1. Falls are taken in full.

    If the purchase price is unknown (older squads), the current price is used.
    """
    current_price = Decimal(current_price)
    if buy_price is None:
        return current_price
    buy_price = Decimal(buy_price)
    if current_price <= buy_price:
        return current_price
    rise = current_price - buy_price
    profit = (rise / Decimal('0.2')).to_integral_value(rounding=ROUND_FLOOR) * Decimal('0.1')
    return buy_price + profit


def check_budget(bank, sold_values, bought_prices):
    """Can the team afford these changes? Returns (bank after the changes, errors).

    bank: money in the bank now.
    sold_values: what the team gets for each player it sells.
    bought_prices: today's price of each player it buys.
    """
    available = Decimal(bank) + sum((Decimal(v) for v in sold_values), Decimal('0.0'))
    cost = sum((Decimal(p) for p in bought_prices), Decimal('0.0'))
    new_bank = available - cost
    errors = []
    if new_bank < 0:
        errors.append(
            f"You can't afford these players. They cost £{cost}m, but you only have "
            f"£{available}m to spend (your bank plus what you get for the players you sell)."
        )
    return new_bank, errors