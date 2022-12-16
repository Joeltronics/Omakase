from cards import Cards
import random
import copy

# Standard deck distribution (108 cards)
_std_deck = {
	Cards.Tempura: 14,
	Cards.Sashimi: 14,
	Cards.Dumpling: 14,
	Cards.Maki2: 12,
	Cards.Maki3: 8,
	Cards.Maki1: 6,
	Cards.SalmonNigiri: 10,
	Cards.SquidNigiri: 5,
	Cards.EggNigiri: 5,
	Cards.Pudding: 10,
	Cards.Wasabi: 6,
	Cards.Chopsticks: 4
}


def get_deck_distribution():
	return copy.deepcopy(_std_deck)


class Deck:
	def __init__(self, distribution):
		self.deck = []
		for card in distribution.keys():
			self.deck += [card] * distribution[card]
		random.shuffle(self.deck)

	def deal_hand(self, num_cards):

		if len(self.deck) < num_cards:
			raise OverflowError("Not enough cards in deck")

		hand = self.deck[0:num_cards]
		self.deck = self.deck[num_cards:]
		return hand

	def deal_hands(self, num_players, num_cards_per_player):
		hands = []
		for _ in range(num_players):
			hands.append(self.deal_hand(num_cards_per_player))
		return hands
