#!/usr/bin/env python3

from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from copy import copy
import itertools
import random
from typing import Tuple, List, Optional, Set

from cards import Card, Pick, Plate


FLOAT_EPSILON = 1e-6


def random_bool() -> bool:
	return bool(random.getrandbits(1))


def count_card(cards: Iterable[Card], card: Card) -> int:
	if isinstance(cards, Sequence):
		return cards.count(card)
	else:
		return sum(c == card for c in cards)


def random_order_and_inverse(num_players) -> Tuple[List[int], List[int]]:
	order = list(range(num_players))
	random.shuffle(order)
	inverse_order = [order.index(idx) for idx in range(num_players)]
	return order, inverse_order


def _prune_likely_bad_picks(options: set[Card]) -> None:

	# Eliminate obvious picks
	# 99% of the time there's no point taking a lower-value nigiri or maki if a higher value is available
	# There could be very rare cases where it's advantageous to take a lower value, hence why this is optional

	# Here we still allow taking cards that don't help us (e.g. Sashimi that's impossible to complete), because a) it
	# might still be useful to block someone else, and b) we don't have enough information to know that anyway

	if Card.SquidNigiri in options:
		options.discard(Card.SalmonNigiri)
		options.discard(Card.EggNigiri)
	elif Card.SalmonNigiri in options:
		options.discard(Card.EggNigiri)

	if Card.Maki3 in options:
		options.discard(Card.Maki2)
		options.discard(Card.Maki1)
	elif Card.Maki2 in options:
		options.discard(Card.Maki1)


def get_chopstick_picks(hand: Collection[Card], num_unused_wasabi: Optional[int], prune_likely_bad_picks=False) -> Set[Pick]:

	# There's no point to using chopsticks to take more chopsticks, so remove these first (before taking combinations)
	# Except for odd case of 2 chopsticks, which we will add back later (after calculating combinations)
	num_chopsticks_in_hand = count_card(hand, Card.Chopsticks)
	card_options = [card for card in hand if card != Card.Chopsticks]

	if len(card_options) < 2:
		if num_chopsticks_in_hand >= 2:
			# Extremely rare case - but it's technically meaningful so we should still return it
			return {Pick(Card.Chopsticks, Card.Chopsticks)}
		return set()

	# Order only matters when nigiri + wasabi is involved (either a wasabi from before, or a new one)
	# So take all combinations (not permuations), then manually add swapped-order pairs that matter after

	if not prune_likely_bad_picks:
		choices = {Pick(*choice) for choice in itertools.combinations(card_options, 2)}
	else:
		first_card_options = set(card_options)
		_prune_likely_bad_picks(first_card_options)
		choices = set()
		for first_card in first_card_options:
			second_card_choices = copy(card_options)
			second_card_choices.remove(first_card)
			second_card_choices = set(second_card_choices)
			_prune_likely_bad_picks(second_card_choices)
			for second_card in second_card_choices:
				choices.add(Pick(*sorted((first_card, second_card))))

	swapped_choices = set()
	if (num_unused_wasabi is None) or (num_unused_wasabi <= 1):
		for card_a, card_b in choices:
			if card_a == card_b:
				continue
			if (num_unused_wasabi is None) or (num_unused_wasabi == 1):
				# If there's already 1 unused wasabi, then the order of 2 different nigiri matters
				if card_a.is_nigiri() and card_b.is_nigiri() and card_a != card_b:
					swapped_choices.add(Pick(card_b, card_a))
			if not num_unused_wasabi:
				# If no wasabi, then the order we play wasabi & nigiri matters
				if (card_a == Card.Wasabi and card_b.is_nigiri()) or (card_a.is_nigiri() and card_b == Card.Wasabi):
					swapped_choices.add(Pick(card_b, card_a))
	choices |= swapped_choices

	if num_chopsticks_in_hand >= 2:
		choices.add(Pick(Card.Chopsticks, Card.Chopsticks))

	return choices


def get_all_picks(
		hand: Collection[Card],
		plate: Plate,
		prune_likely_bad_picks = False,
		) -> Set[Pick]:

	can_use_chopsticks = plate.chopsticks and len(hand) > 1

	if prune_likely_bad_picks:
		if can_use_chopsticks and len(hand) <= (1 + plate.chopsticks) and (Card.Chopsticks not in hand):
			# If this is the last time we can use these chopsticks, then no reason not to - don't bother including non-chopstick picks
			options = set()
		else:
			options = {card for card in hand}
			# Don't take chopsticks if we can't use them (unless they're the only option)
			if len(hand) <= 1 + plate.chopsticks and len(options) > 1:
				options.discard(Card.Chopsticks)
			_prune_likely_bad_picks(options)
			options = {Pick(card) for card in options}
	else:
		options = {Pick(card) for card in hand}

	if can_use_chopsticks:
		options |= get_chopstick_picks(
			hand, num_unused_wasabi=plate.unused_wasabi, prune_likely_bad_picks=prune_likely_bad_picks)

	assert options
	return options


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
