#!/usr/bin/env python3

from collections import Counter
from collections.abc import Collection, Iterable, Sequence
import itertools
import random
from typing import Tuple, List, Set

from cards import Card


FLOAT_EPSILON = 1e-6


def random_bool() -> bool:
	return bool(random.getrandbits(1))


def count_card(cards: Iterable[Card], card: Card) -> int:
	if isinstance(cards, Sequence):
		return cards.count(card)
	else:
		return len([c for c in cards if c == card])


def get_num_unused_wasabi(plate: Sequence[Card]) -> int:
	n = 0
	for card in plate:
		if card == Card.Wasabi:
			n += 1
		elif n > 0 and card.is_nigiri():
			n -= 1
	return n


def get_num_sashimi_needed(plate: Collection[Card]) -> int:
	return 3 - (count_card(plate, Card.Sashimi) % 3)


def get_num_tempura_needed(plate: Collection[Card]) -> int:
	return 2 - (count_card(plate, Card.Tempura) % 2)


def random_order_and_inverse(num_players) -> Tuple[List[int], List[int]]:
	order = list(range(num_players))
	random.shuffle(order)
	inverse_order = [order.index(idx) for idx in range(num_players)]
	return order, inverse_order


def meaningful_chopstick_pairs(hand: Collection[Card], num_unused_wasabi: int) -> Set[Tuple[Card, Card]]:

	# TODO: Add an option to eliminate obvious picks (no point taking a lower-value nigiri or maki if a higher-value is available)
	# Make sure it's optional though - there could be very rare cases where it's advantageous to take a lower value

	# There's no point to using chopsticks to take more chopsticks, so remove these first (before taking combinations)
	# Except for odd case of 2 chopsticks, which we will add back later (after calculating combinations)
	num_chopsticks_in_hand = count_card(hand, Card.Chopsticks)
	card_options = [card for card in hand if card != Card.Chopsticks]

	if len(card_options) < 2:
		if num_chopsticks_in_hand >= 2:
			# Extremely rare case - but it's technically meaningful so we should still return it
			return {(Card.Chopsticks, Card.Chopsticks)}
		return set()

	# Order only matters when nigiri + wasabi is involved (either a wasabi from before, or a new one)
	# So take all combinations (not permuations), then manually add swapped-order pairs that matter after

	choices = set(itertools.combinations(card_options, 2))

	swapped_choices = set()
	if num_unused_wasabi <= 1:
		for card_a, card_b in choices:
			if card_a == card_b:
				continue
			if num_unused_wasabi == 1:
				# If there's already 1 unused wasabi, then the order of 2 different nigiri matters
				if card_a.is_nigiri() and card_b.is_nigiri() and card_a != card_b:
					swapped_choices.add((card_b, card_a))
			elif not num_unused_wasabi:
				# If no wasabi, then the order we play wasabi & nigiri matters
				if (card_a == Card.Wasabi and card_b.is_nigiri()) or (card_a.is_nigiri() and card_b == Card.Wasabi):
					swapped_choices.add((card_b, card_a))

	if num_chopsticks_in_hand >= 2:
		choices.add((Card.Chopsticks, Card.Chopsticks))

	return choices | swapped_choices


def add_numbers_to_duplicate_names(player_names: Sequence[str]) -> List[str]:
	player_names_count = Counter(player_names)
	name_numbers = {name: 1 for name, count in player_names_count.items() if count > 1}

	ret = []
	for name in player_names:
		if name in name_numbers:
			ret.append(f'{name} {name_numbers[name]}')
			name_numbers[name] += 1
		else:
			ret.append(name)

	# Could run into problems if passed in a name already ending with a number
	# e.g.: ["Player", "Player", "Player 1"] would end up with duplicate: ["Player 1", "Player 2", "Player 1"]
	# TODO: handle this case
	if len(ret) != len(set(ret)):
		raise ValueError(f'Invalid player names: {player_names}')

	return ret


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
