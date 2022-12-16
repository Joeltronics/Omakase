import copy
import random
from utils import *
from cards import *

use_named_players = False

# If this is true, playing a nigiri on a wasabi replaces it with a "x with Wasabi" card
# If false, have to manually factor plate order into scoring
# Everything (currently) is coded so that either format should work
# Mostly just rely on PlayerState.get_num_unused_wasabi()
# I've left both in because I'm not sure which will make AI lookahead coding easier
use_wasabi_card_variants = True

_num_players = 0

# Want all names to be same length just for neater formatting

_player_names = ["Geoff", "Steve", "Tracy", "Johan", "James", "Paula", "Jenni", "Julia", "Nancy", "Bobby"]
#_player_names = ["Eddard", "Tyrion", "Cersei", "Robert", "Tommen", "Walder", "Rickon", "Olenna", "Chewie"]
#_player_names = ["Jaime", "Sansa", "Roose", "Walda", "Davos", "Hodor", "Varys", "Petyr", "Loras", "Renly", "Tyene"]
#_player_names = ["Arya", "Bran", "Robb", "Dany", "Lady", "Luke", "Mara", "R2D2", "C3PO", "Kylo"]


def get_player_name():
	global _num_players
	_num_players += 1

	if use_named_players:
		global _player_names
		n = random.randint(0, len(_player_names) - 1)
		return _player_names.pop(n)
	else:
		return "Player %i" % _num_players


class PlayerState:
	def __init__(self, deck_dist, name=None):

		# Public info
		if not name:
			name = get_player_name()
		self.name = name
		self.plate = []
		self.total_score = 0
		self.num_pudding = 0

		# Knowledge of deck and other players' state
		self.deck_dist = copy.deepcopy(deck_dist)
		self.other_player_states = None
		self.num_unseen_dealt_cards = None

		# Private info
		self.hand = None

	def assign_hand(self, hand):
		# Sorting not actually necessary, but helps print formatting
		self.hand = sort_cards(hand)

	def update_deck_dist(self, cards_to_remove):

		def remove_one(card):
			if self.deck_dist[card] <= 0:
				raise AssertionError('Cannot remove card from deck, already empty')

			if self.num_unseen_dealt_cards <= 0:
				raise AssertionError('Trying to remove cards already seen from deck distribution')

			self.num_unseen_dealt_cards -= 1
			self.deck_dist[card] -= 1

		if hasattr(cards_to_remove, "__iter__"):

			# This would also get triggered by case in remove_one, but this way we'll give a better error message
			if len(cards_to_remove) > self.num_unseen_dealt_cards:
				raise AssertionError("Trying to remove %i cards from deck dist when only %i unseen cards left"
					% (len(cards_to_remove), self.num_unseen_dealt_cards))

			for card_to_remove in cards_to_remove:
				# Not going with recursive here will break using this on lists of lists,
				# but you probably shouldn't be using it that way anyway
				remove_one(card_to_remove)
		else:
			remove_one(cards_to_remove)

	def get_num_players(self):
		if not self.other_player_states:
			raise AssertionError("Cannot call get_num_players before initializing player state")
		return 1 + len(self.other_player_states)

	# Returns copy with all the same public info - but hand is secret
	def get_public_copy(self):
		self_copy = copy.copy(self)
		assert self_copy.plate is self.plate
		self_copy.hand = None
		return self_copy

	def get_num_unused_wasabi(self):
		n = 0
		for card in self.plate:
			if card == Cards.Wasabi:
				n += 1
			elif n > 0 and card in [Cards.EggNigiri, Cards.SalmonNigiri, Cards.SquidNigiri]:
				n -= 1
		return n

	def play_card(self, card):

		if card not in self.hand:
			raise ValueError('Cannot play card %s, not in hand: %s' % (card, self.hand))

		remove_first_instance(self.hand, card)

		if use_wasabi_card_variants and self.get_num_unused_wasabi() > 0 and \
				card in [Cards.EggNigiri, Cards.SalmonNigiri, Cards.SquidNigiri]:
			card = add_wasabi(card, throw_if_cant=True)
			remove_first_instance(self.plate, Cards.Wasabi)

		# Have to still add to plate
		self.plate.append(card)

		if card == Cards.Pudding:
			self.num_pudding += 1

	def end_round(self, score):
		self.total_score += score
		self.plate = []

	def update_other_player_state_before_pass(self, verbose=False):

		# DEBUG
		if True and verbose:
			print('%s state before update:' % self.name)
			print(repr(self))
			print()

		# Remove last played card from knowledge of hands

		for state in self.other_player_states:
			last_played_card = state.plate[-1]
			last_played_card = remove_wasabi(last_played_card, throw_if_cant=False)
			if state.hand:
				remove_first_instance(state.hand, last_played_card)
			else:
				self.update_deck_dist(last_played_card)

		# DEBUG
		if True and verbose:
			print('%s state after removing, before shift:' % self.name)
			print(repr(self))
			print()

		# Shift hands

		for n in reversed(range(len(self.other_player_states)-1)):
			self.other_player_states[n+1].hand = self.other_player_states[n].hand
		self.other_player_states[0].hand = copy.deepcopy(self.hand)

		if verbose:
			print('%s state: (own hand will be previous)' % self.name)
			print(repr(self))
			print()

	def update_other_player_state_after_pass(self, verbose=False):
		# If there are still unseen cards, then this must be a new hand
		if self.num_unseen_dealt_cards > 0:
			self.update_deck_dist(self.hand)

		if verbose:
			print('%s state:' % self.name)
			print(repr(self))
			print()

	def __str__(self):
		return "(%s: plate %s, hand %s, pudding %i, score %i)" % (
			self.name,
			card_names(self.plate, sort=False),
			card_names(self.hand, sort=False),
			self.num_pudding,
			self.total_score)

	def __repr__(self):

		s = "---- %s state ----\n" % self.name

		s += "plate %s, hand %s, pudding %i, score %i,\n" % (
			card_names(self.plate, sort=False),
			card_names(self.hand, sort=False),
			self.num_pudding,
			self.total_score)

		if self.other_player_states:
			for state in self.other_player_states:
				s += "%s: plate %s, hand %s, pudding %i, score %i,\n" % (
					state.name,
					card_names(state.plate, sort=False),
					card_names(state.hand, sort=False),
					state.num_pudding,
					state.total_score)

		s += "deck_dist: %s, %i unseen dealt cards\n" % (dict_card_names(self.deck_dist), self.num_unseen_dealt_cards)

		s += "-- end %s state --\n" % self.name

		return s


def init_other_player_states(players, forward=True, omniscient=False):

	players_list = players if forward else list(reversed(players))

	num_players = len(players)
	for n, player in enumerate(players_list):

		if not player.hand:
			raise AssertionError("Must assign hands before calling init_other_player_states")

		if player.num_unseen_dealt_cards:
			raise AssertionError("num_unseen_dealt_cards nonzero at start")

		player.num_unseen_dealt_cards = len(player.hand)
		player.update_deck_dist(player.hand)
		assert player.num_unseen_dealt_cards == 0

		player.other_player_states = []
		for m in range(num_players-1):
			# Start with player after the current one
			idx = (n + m + 1) % num_players
			state = players_list[idx].get_public_copy()

			player.num_unseen_dealt_cards += len(players_list[idx].hand)
			if omniscient:
				state.hand = copy.deepcopy(players_list[idx].hand)
				player.update_deck_dist(state.hand)

			player.other_player_states.append(state)

		if omniscient:
			assert player.num_unseen_dealt_cards == 0
		else:
			print("%s, %i unseen cards" % (player.name, player.num_unseen_dealt_cards))


def pass_hands(players, forward=True):
	last_player_idx = len(players) - 1
	if forward:
		swap_hand = players[last_player_idx].hand
		for n in range(last_player_idx, 0, -1):
			players[n].hand = players[n - 1].hand
		players[0].hand = swap_hand
	else:
		swap_hand = players[0].hand
		for n in range(0, last_player_idx, 1):
			players[n].hand = players[n + 1].hand
		players[last_player_idx].hand = swap_hand

"""
def _test():
	import deck
	deck_dist = deck.get_deck_distribution()
	test_deck = deck.Deck(deck_dist)

	players =

	init_other_player_states(players, forward=True, omniscient=False)


_test()
"""
