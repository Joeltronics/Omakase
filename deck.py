#!/usr/bin/env python

from copy import copy
import random
from typing import List


from cards import Card


# Standard deck distribution (108 cards)
_std_deck = {
	Card.Tempura: 14,
	Card.Sashimi: 14,
	Card.Dumpling: 14,
	Card.Maki2: 12,
	Card.Maki3: 8,
	Card.Maki1: 6,
	Card.SalmonNigiri: 10,
	Card.SquidNigiri: 5,
	Card.EggNigiri: 5,
	Card.Pudding: 10,
	Card.Wasabi: 6,
	Card.Chopsticks: 4
}


def get_deck_distribution():
	return copy(_std_deck)


class Deck:
	def __init__(self, distribution: dict):
		self.deck = []
		for card in distribution.keys():
			self.deck += [card] * distribution[card]
		random.shuffle(self.deck)

	def deal_hand(self, num_cards: int) -> List[Card]:

		if len(self.deck) < num_cards:
			raise OverflowError("Not enough cards in deck")

		hand = self.deck[0:num_cards]
		self.deck = self.deck[num_cards:]
		return hand

	def deal_hands(self, num_players: int, num_cards_per_player: int) -> List[List[Card]]:
		hands = []
		for _ in range(num_players):
			hands.append(self.deal_hand(num_cards_per_player))
		return hands
