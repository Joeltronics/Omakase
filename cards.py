#!/usr/bin/env python


from enum import Enum, unique
from typing import Any, Dict, Iterable, List, Union, Tuple, Optional


@unique
class Card(Enum):

	Unknown = '?'

	Tempura = 'Tempura'
	Sashimi = 'Sashimi'
	Dumpling = 'Dumpling'
	Maki1 = '1 Maki'
	Maki2 = '2 Maki'
	Maki3 = '3 Maki'
	EggNigiri = 'Egg Nigiri'
	SalmonNigiri = 'Salmon Nigiri'
	SquidNigiri = 'Squid Nigiri'
	Wasabi = 'Wasabi'
	Pudding = 'Pudding'
	Chopsticks = 'Chopsticks'

	def __str__(self) -> str:
		return self.value

	def is_maki(self) -> bool:
		return self in [Card.Maki1, Card.Maki2, Card.Maki3]

	def is_nigiri(self) -> bool:
		return self in [Card.EggNigiri, Card.SalmonNigiri, Card.SquidNigiri]

	def num_maki(self) -> Optional[int]:
		if self == Card.Maki1:
			return 1
		elif self == Card.Maki2:
			return 2
		elif self == Card.Maki3:
			return 3
		else:
			return None


def card_sort_order(card):
	return {
		Card.Sashimi: 1,
		Card.Tempura: 2,
		Card.Dumpling: 3,
		Card.SquidNigiri: 4,
		Card.SalmonNigiri: 5,
		Card.EggNigiri: 6,
		Card.Wasabi: 7,
		Card.Maki3: 8,
		Card.Maki2: 9,
		Card.Maki1: 10,
		Card.Pudding: 11,
		Card.Chopsticks: 12,

		Card.Unknown: 99,
	}[card]


def sort_cards(cards: Iterable[Card]) -> List[Card]:
	return sorted(list(cards), key=card_sort_order)


def card_names(cards: Iterable[Union[Card, Tuple[Card, Card]]], sort=False):

	if not cards:
		return "[]"

	# TODO: if sorted, count uniques - e.g. display "[2 Tempura]" instead of "[Tempura, Tempura]"

	display_list = sorted(list(cards), key=card_sort_order) if sort else cards

	return "[" + ", ".join([str(card) for card in display_list]) + "]"


def dict_card_names(cards: Dict[Card, Any], sort=True):

	keys = cards.keys()
	if sort:
		keys = sort_cards(keys)

	dict_list = [f"{card}: {cards[card]}" for card in keys]

	return "{" + ", ".join(dict_list) + "}"
