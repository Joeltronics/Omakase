#!/usr/bin/env python3

import random
from typing import Iterable, Tuple, List

from cards import Card


def count_card(plate: Iterable[Card], card: Card) -> int:
	return len([c for c in plate if c == card])


def random_order_and_inverse(num_players) -> Tuple[List[int], List[int]]:
	order = list(range(num_players))
	random.shuffle(order)
	inverse_order = [order.index(idx) for idx in range(num_players)]
	return order, inverse_order


def _test():
	for seed in range(4):
		random.seed(seed)
		order, inverse_order = random_order_and_inverse(5)
		original = ['A', 'B', 'C', 'D', 'E']
		shuffled = [original[idx] for idx in order]
		if order != [0, 1, 2, 3, 4]:
			assert shuffled != original
		deshuffled = [shuffled[idx] for idx in inverse_order]
		assert deshuffled == original
	random.seed()

_test()
