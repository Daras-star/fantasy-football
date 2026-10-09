from decimal import Decimal

from django.test import SimpleTestCase

from fantasy.transfers import (
    check_budget, next_free_transfers, selling_price, transfer_cost, transfers_made,
)


class TransferCountTests(SimpleTestCase):
    def test_counts_players_swapped_out(self):
        self.assertEqual(transfers_made([1, 2, 3], [1, 2, 4]), 1)
        self.assertEqual(transfers_made([1, 2, 3], [1, 2, 3]), 0)
        self.assertEqual(transfers_made([1, 2, 3], [4, 5, 6]), 3)


class TransferCostTests(SimpleTestCase):
    def test_free_transfers_cost_nothing(self):
        self.assertEqual(transfer_cost(0, 1), 0)
        self.assertEqual(transfer_cost(1, 1), 0)
        self.assertEqual(transfer_cost(2, 5), 0)

    def test_extra_transfers_cost_four_each(self):
        self.assertEqual(transfer_cost(2, 1), 4)
        self.assertEqual(transfer_cost(3, 2), 4)
        self.assertEqual(transfer_cost(4, 1), 12)


class FreeTransferBankTests(SimpleTestCase):
    def test_unused_transfer_is_banked(self):
        self.assertEqual(next_free_transfers(1, 0), 2)
        self.assertEqual(next_free_transfers(2, 0), 3)

    def test_using_the_free_transfer_resets_to_one(self):
        self.assertEqual(next_free_transfers(1, 1), 1)

    def test_hits_never_push_it_below_one(self):
        self.assertEqual(next_free_transfers(1, 3), 1)

    def test_bank_stops_at_five(self):
        self.assertEqual(next_free_transfers(5, 0), 5)

    def test_partly_used_bank(self):
        self.assertEqual(next_free_transfers(3, 1), 3)


class SellingPriceTests(SimpleTestCase):
    def test_no_change(self):
        self.assertEqual(selling_price('5.0', '5.0'), Decimal('5.0'))

    def test_falls_are_taken_in_full(self):
        self.assertEqual(selling_price('5.0', '4.8'), Decimal('4.8'))

    def test_you_keep_half_the_rise_rounded_down(self):
        self.assertEqual(selling_price('5.0', '5.1'), Decimal('5.0'))
        self.assertEqual(selling_price('5.0', '5.3'), Decimal('5.1'))
        self.assertEqual(selling_price('5.0', '5.4'), Decimal('5.2'))
class UnknownPurchasePriceTests(SimpleTestCase):
    def test_current_price_is_used_when_the_purchase_price_is_unknown(self):
        self.assertEqual(selling_price(None, '5.2'), Decimal('5.2'))


class BudgetCheckTests(SimpleTestCase):
    def test_an_affordable_swap(self):
        new_bank, errors = check_budget('0.5', ['5.0'], ['5.5'])
        self.assertEqual(new_bank, Decimal('0.0'))
        self.assertEqual(errors, [])

    def test_a_swap_that_costs_too_much_is_refused(self):
        new_bank, errors = check_budget('0.5', ['5.0'], ['5.6'])
        self.assertEqual(new_bank, Decimal('-0.1'))
        self.assertEqual(len(errors), 1)

    def test_no_changes_leaves_the_bank_alone(self):
        self.assertEqual(check_budget('2.0', [], []), (Decimal('2.0'), []))