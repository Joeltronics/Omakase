#!/usr/bin/env python

from collections.abc import Sequence
from dataclasses import dataclass

from enum import IntEnum, unique
from typing import Any, Dict, Iterable, List, Literal, Union, Tuple, Optional


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
			Card.Maki1: 'Maki 1',
			Card.Maki2: 'Maki 2',
			Card.Maki3: 'Maki 3',
			Card.EggNigiri: 'Egg Nigiri',
			Card.SalmonNigiri: 'Salmon Nigiri',
			Card.SquidNigiri: 'Squid Nigiri',
			Card.Wasabi: 'Wasabi',
			Card.Pudding: 'Pudding',
			Card.Chopsticks: 'Chopsticks',
		}[self]

	def short_name(self) -> str:
		return {
			Card.Unknown: '???',
			Card.Tempura: 'TEM',
			Card.Sashimi: 'SAS',
			Card.Dumpling: 'DUM',
			Card.Maki1: 'MA1',
			Card.Maki2: 'MA2',
			Card.Maki3: 'MA3',
			Card.EggNigiri: 'EGG',
			Card.SalmonNigiri: 'SAL',
			Card.SquidNigiri: 'SQU',
			Card.Wasabi: 'WAS',
			Card.Pudding: 'PUD',
			Card.Chopsticks: 'CHO',
		}[self]

	def is_maki(self) -> bool:
		return self in [Card.Maki1, Card.Maki2, Card.Maki3]

	def is_nigiri(self) -> bool:
		return self in [Card.EggNigiri, Card.SalmonNigiri, Card.SquidNigiri]

	def num_maki(self) -> Literal[0, 1, 2, 3]:
		if self == Card.Maki1:
			return 1
		elif self == Card.Maki2:
			return 2
		elif self == Card.Maki3:
			return 3
		else:
			return 0

	def nigiri_base_points(self) -> Optional[Literal[1, 2, 3]]:
		if self == Card.EggNigiri:
			return 1
		elif self == Card.SalmonNigiri:
			return 2
		elif self == Card.SquidNigiri:
			return 3
		else:
			return None


def sort_cards(cards: Iterable[Card]) -> List[Card]:
	return sorted(list(cards))


class Pick(Sequence[Card]):
	__slots__ = ['_a', '_b']

	def __init__(self, a: Card, b: Optional[Card]=None, /):
		if (b is not None) and not self._order_may_matter(a=a, b=b):
			a, b = sorted((a, b))
		assert isinstance(a, Card)
		assert (b is None) or isinstance(b, Card)
		self._a: Card = a
		self._b: Optional[Card] = b

	@property
	def a(self) -> Card:
		return self._a

	@property
	def b(self) -> Optional[Card]:
		return self._b

	def as_tuple(self) -> Union[Tuple[Card], Tuple[Card, Card]]:
		if self._b is None:
			return (self._a,)
		else:
			return (self._a, self._b)

	def as_pair(self) -> Tuple[Card, Optional[Card]]:
		return (self._a, self._b)

	def order_matters(self, num_unused_wasabi: int) -> bool:

		if num_unused_wasabi < 0:
			raise ValueError('num_unused_wasabi must be >= 0')

		# Order matters if:
		#   no unused wasabi: wasabi + nigiri
		#   1 unused wasabi: 2 different nigiri

		if (self._b is None) or (self._a == self._b):
			return False

		a_nigiri = self._a.is_nigiri()
		b_nigiri = self._b.is_nigiri()
		a_wasabi = self._a == Card.Wasabi
		b_wasabi = self._b == Card.Wasabi

		if not num_unused_wasabi:
			return (a_wasabi and b_nigiri) or (b_wasabi and a_nigiri)
		elif num_unused_wasabi == 1:
			return a_nigiri and b_nigiri
		else:
			return False

	@staticmethod
	def _order_may_matter(a: Card, b: Optional[Card]) -> bool:
		if (b is None) or (a == b):
			return False
		a_nigiri = a.is_nigiri()
		b_nigiri = b.is_nigiri()
		a_wasabi = a == Card.Wasabi
		b_wasabi = b == Card.Wasabi
		return (a_nigiri and b_nigiri) or (a_wasabi and b_nigiri) or (b_wasabi and a_nigiri)

	@property
	def order_may_matter(self) -> bool:
		return self._order_may_matter(a=self._a, b=self._b)

	def __getitem__(self, idx: int) -> Optional[Card]:
		return self.as_tuple()[idx]

	def __len__(self) -> Literal[1, 2]:
		return 2 if (self._b is not None) else 1

	def __contains__(self, card: Card) -> bool:
		return card in self.as_pair()

	def __eq__(self, other: Union['Pick', Card]) -> bool:
		if isinstance(other, Card):
			return (self._b is None) and (self._a == other)
		else:
			return self.as_pair() == other.as_pair()

	def __hash__(self) -> int:
		if self._b is None:
			return hash(self._a)
		else:
			return hash(self.as_pair())

	def __str__(self) -> str:
		if self._b is None:
			return str(self._a)
		return f'{self._a} + {self._b}'

	def short_name(self) -> str:
		if self._b is None:
			return self._a.short_name()
		return f'{self._a.short_name()} + {self._b.short_name()}'

	def __repr__(self) -> str:
		return f'Pick(a={self._a}, b={self._b}, order_may_matter={self.order_may_matter})'


# TODO: python 3.10 slots=True
@dataclass
class Plate:
	score: int = 0
	maki: int = 0
	chopsticks: int = 0
	unused_wasabi: int = 0
	unscored_sashimi: int = 0
	unscored_tempura: bool = False
	dumplings: int = 0

	@property
	def num_sashimi_needed(self) -> Literal[1, 2, 3]:
		return [3, 2, 1][self.unscored_sashimi]

	@property
	def num_tempura_needed(self) -> Literal[1, 2]:
		return 1 if self.unscored_tempura else 2

	def clear(self) -> None:
		self.score = 0
		self.maki = 0
		self.chopsticks = 0
		self.unused_wasabi = 0
		self.unscored_sashimi = 0
		self.unscored_tempura = False
		self.dumplings = 0

	def __bool__(self) -> bool:
		# self.dumplings is excluded, since if this is nonzero, score would be nonzero too
		return self.score or self.maki or self.chopsticks or self.unused_wasabi or self.unscored_sashimi or self.unscored_tempura

	def __str__(self) -> str:
		
		vals = []

		if self.score:
			vals.append(f'{self.score} scored points')

		if self.maki:
			vals.append(f'{self.maki} Maki')

		if self.chopsticks:
			vals.append(f'{self.chopsticks} Chopsticks')

		if self.unused_wasabi:
			vals.append(f'{self.unused_wasabi} unused Wasabi')

		if self.unscored_sashimi:
			vals.append(f'{self.unscored_sashimi} Sashimi')

		if self.unscored_tempura:
			vals.append('1 Tempura')

		if self.dumplings:
			vals.append(f'{self.dumplings} dumplings (scored)')

		return '[' + ', '.join(vals) + ']'

	def add(self, card: Card) -> None:
		if card == Card.Chopsticks:
			self.chopsticks += 1

		elif card == Card.Wasabi:
			self.unused_wasabi += 1

		elif card == Card.Sashimi:
			if self.unscored_sashimi == 2:
				self.score += 10
				self.unscored_sashimi = 0
			else:
				self.unscored_sashimi += 1

		elif card == Card.Tempura:
			if self.unscored_tempura:
				self.score += 5
			self.unscored_tempura = not self.unscored_tempura

		elif card == Card.Dumpling:
			assert 0 <= self.dumplings <= 5
			if self.dumplings >= 5:
				return
			self.score += 1 + self.dumplings
			self.dumplings += 1

		elif card.is_nigiri():
			points = card.nigiri_base_points()
			assert points is not None
			if self.unused_wasabi:
				self.unused_wasabi -= 1
				points *= 3
			self.score += points

		elif card.is_maki():
			num_maki = card.num_maki()
			assert num_maki
			self.maki += num_maki

		elif card == Card.Pudding:
			pass  # Ignore puddings

		else:
			raise ValueError(f'Invalid card: {card}')

	def play(self, pick: Pick) -> None:
		if len(pick) == 2:
			if not self.chopsticks:
				raise ValueError('Cannot play 2 cards without chopsticks on plate!')
			self.chopsticks -= 1
		for card in pick:
			self.add(card)


def card_names(
		cards: Union[Plate, Iterable[Union[Card, Tuple[Card, Card], Pick]]],
		sort=False,
		short=False,
		) -> str:

	if isinstance(cards, Plate):
		return str(cards)

	if isinstance(cards, (set, frozenset)):
		start_chr = '{'
		end_chr = '}'
	else:
		start_chr = '['
		end_chr = ']'

	if not cards:
		return start_chr + end_chr

	# TODO: if sorted, count uniques - e.g. display "[2 Tempura]" instead of "[Tempura, Tempura]"
	display_list = sorted(list(cards)) if sort else cards

	if short:
		display_list = [card.short_name() for card in display_list]
	else:
		display_list = [str(card) for card in display_list]

	return start_chr + ", ".join(display_list) + end_chr


def dict_card_names(cards: Dict[Card, Any], sort=True, short=False) -> str:

	keys = cards.keys()
	if sort:
		keys = sort_cards(keys)

	if short:
		dict_list = [f"{card.short_name()}: {cards[card]}" for card in keys]
	else:
		dict_list = [f"{card}: {cards[card]}" for card in keys]

	return "{" + ", ".join(dict_list) + "}"
