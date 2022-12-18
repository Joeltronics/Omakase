#!/usr/bin/env python


from enum import Enum, unique
from typing import Any, Dict, Iterable, List


@unique
class Card(Enum):
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

	# These aren't "real" cards that can go into the deck, but a card
	# can get converted into one when played
	WasabiEggNigiri = 'Egg Nigiri w/ Wasabi'
	WasabiSalmonNigiri = 'Salmon Nigiri w/ Wasabi'
	WasabiSquidNigiri = 'Squid Nigiri w/ Wasabi'

	def __str__(self) -> str:
		return self.value


def remove_wasabi(card, throw_if_cant=True):
	if card == Card.WasabiSquidNigiri:
		return Card.SquidNigiri
	elif card == Card.WasabiSalmonNigiri:
		return Card.SalmonNigiri
	elif card == Card.WasabiEggNigiri:
		return Card.EggNigiri
	else:
		if throw_if_cant:
			raise ValueError(f'Cannot remove wasabi from {card}')
		return card


def add_wasabi(card, throw_if_cant=True):
	if card == Card.SquidNigiri:
		return Card.WasabiSquidNigiri
	elif card == Card.SalmonNigiri:
		return Card.WasabiSalmonNigiri
	elif card == Card.EggNigiri:
		return Card.WasabiEggNigiri
	else:
		if throw_if_cant:
			raise ValueError(f'Cannot add wasabi to {card}')
		return card


def card_sort_order(card):
	return {
		Card.Sashimi: 1,
		Card.Tempura: 2,
		Card.Dumpling: 3,
		Card.WasabiSquidNigiri: 4,
		Card.WasabiSalmonNigiri: 5,
		Card.WasabiEggNigiri: 6,
		Card.SquidNigiri: 7,
		Card.SalmonNigiri: 8,
		Card.EggNigiri: 9,
		Card.Wasabi: 10,
		Card.Maki3: 11,
		Card.Maki2: 12,
		Card.Maki1: 13,
		Card.Pudding: 14,
		Card.Chopsticks: 15,
	}[card]


def sort_cards(cards: Iterable[Card]) -> List[Card]:
	return sorted(list(cards), key=card_sort_order)


def card_names(cards: Iterable[Card], sort=False):

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
