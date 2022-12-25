#!/usr/bin/env python


from enum import IntEnum, unique
from typing import Any, Dict, Iterable, List, Union, Tuple, Optional


@unique
class Card(IntEnum):

	Sashimi = 1
	Tempura = 2
	Dumpling = 3
	SquidNigiri = 4
	SalmonNigiri = 5
	EggNigiri = 6
	Wasabi = 7
	Maki3 = 8
	Maki2 = 9
	Maki1 = 10
	Pudding = 11
	Chopsticks = 12

	Unknown = 99

	def __str__(self) -> str:
		return {
			Card.Unknown: '?',
			Card.Tempura: 'Tempura',
			Card.Sashimi: 'Sashimi',
			Card.Dumpling: 'Dumpling',
			Card.Maki1: '1 Maki',
			Card.Maki2: '2 Maki',
			Card.Maki3: '3 Maki',
			Card.EggNigiri: 'Egg Nigiri',
			Card.SalmonNigiri: 'Salmon Nigiri',
			Card.SquidNigiri: 'Squid Nigiri',
			Card.Wasabi: 'Wasabi',
			Card.Pudding: 'Pudding',
			Card.Chopsticks: 'Chopsticks',
		}[self]

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


def sort_cards(cards: Iterable[Card]) -> List[Card]:
	return sorted(list(cards))


def card_names(cards: Iterable[Union[Card, Tuple[Card, Card]]], sort=False):

	if not cards:
		return "[]"

	# TODO: if sorted, count uniques - e.g. display "[2 Tempura]" instead of "[Tempura, Tempura]"

	display_list = sorted(list(cards)) if sort else cards

	return "[" + ", ".join([str(card) for card in display_list]) + "]"


def dict_card_names(cards: Dict[Card, Any], sort=True):

	keys = cards.keys()
	if sort:
		keys = sort_cards(keys)

	dict_list = [f"{card}: {cards[card]}" for card in keys]

	return "{" + ", ".join(dict_list) + "}"
