

from enum import Enum, unique

@unique
class Cards(Enum):
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


def remove_wasabi(card, throw_if_cant=True):
	if card == Cards.WasabiSquidNigiri:
		return Cards.SquidNigiri
	elif card == Cards.WasabiSalmonNigiri:
		return Cards.SalmonNigiri
	elif card == Cards.WasabiEggNigiri:
		return Cards.EggNigiri
	else:
		if throw_if_cant:
			raise ValueError('Cannot remove wasabi from %s' % card_name(card))
		return card


def add_wasabi(card, throw_if_cant=True):
	if card == Cards.SquidNigiri:
		return Cards.WasabiSquidNigiri
	elif card == Cards.SalmonNigiri:
		return Cards.WasabiSalmonNigiri
	elif card == Cards.EggNigiri:
		return Cards.WasabiEggNigiri
	else:
		if throw_if_cant:
			raise ValueError('Cannot add wasabi to %s' % card_name(card))
		return card


def card_sort_order(card):
	return {
		Cards.Sashimi: 1,
		Cards.Tempura: 2,
		Cards.Dumpling: 3,
		Cards.WasabiSquidNigiri: 4,
		Cards.WasabiSalmonNigiri: 5,
		Cards.WasabiEggNigiri: 6,
		Cards.SquidNigiri: 7,
		Cards.SalmonNigiri: 8,
		Cards.EggNigiri: 9,
		Cards.Wasabi: 10,
		Cards.Maki3: 11,
		Cards.Maki2: 12,
		Cards.Maki1: 13,
		Cards.Pudding: 14,
		Cards.Chopsticks: 15,
	}[card]


def sort_cards(cards):
	return sorted(list(cards), key=card_sort_order)


def card_name(card):
	return str(card.value)


def card_names(cards, sort=False):

	if not cards:
		return "[]"

	# TODO: if sorted, count uniques, e.g. display "[2 Tempura]" instead of "[Tempura, Tempura]"

	if sort:
		display_list = sorted(list(cards), key=card_sort_order)
	else:
		display_list = cards

	return "[" + ", ".join([card_name(card) for card in display_list]) + "]"


def dict_card_names(cards, sort=True):

	keys = cards.keys()

	if sort:
		keys = sort_cards(keys)

	dict_list = []
	for card in keys:
		dict_list += ["%s: %i" % (card_name(card), cards[card])]

	return "{" + ", ".join(dict_list) + "}"
