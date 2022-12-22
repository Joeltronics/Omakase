#!/usr/bin/env python

import copy
import random
from typing import Optional, List

from utils import *
from cards import Card, sort_cards, card_names, dict_card_names

use_named_players = False

_num_players = 0

# Want all names to be same length just for neater formatting

_player_names = ["Geoff", "Steve", "Tracy", "Johan", "James", "Paula", "Jenny", "Julia", "Nancy", "Bobby"]
#_player_names = ["Eddard", "Tyrion", "Cersei", "Robert", "Tommen", "Walder", "Rickon", "Olenna", "Chewie"]
#_player_names = ["Jaime", "Sansa", "Roose", "Walda", "Davos", "Hodor", "Varys", "Petyr", "Loras", "Renly", "Tyene"]
#_player_names = ["Arya", "Bran", "Robb", "Dany", "Lady", "Luke", "Leia", "Mara", "R2D2", "C3PO", "Kylo"]


def get_player_name() -> str:
	global _num_players
	_num_players += 1

	if use_named_players:
		global _player_names
		n = random.randint(0, len(_player_names) - 1)
		return _player_names.pop(n)
	else:
		return "Player %i" % _num_players


class PlayerState:
	def __init__(self, deck_dist: dict, name=None):

		# Public info
		if not name:
			name = get_player_name()
		self.name = name
		self.plate = []
		self.play_history = []  # History of cards played this round (without chopsticks, would be identical to self.plate)
		self.total_score = 0
		self.num_pudding = 0

		# Knowledge of deck and other players' state
		self.deck_dist = copy.deepcopy(deck_dist)
		self.other_player_states: Optional[List] = None
		self.num_unseen_dealt_cards = None

		# Private info
		self.hand = None

	def assign_hand(self, hand):
		# Sorting not actually necessary, but helps print formatting
		self.hand = sort_cards(hand)

	def update_deck_dist(self, cards_to_remove):

		def remove_one(card):
			if self.deck_dist[card] <= 0:
				raise AssertionError(f'Cannot remove card from deck, already empty; {cards_to_remove=}, {card=}')  # FIXME: this can trigger with chopsticks + non-omniscient

			if self.num_unseen_dealt_cards <= 0:
				raise AssertionError(f'Trying to remove cards already seen from deck distribution; {cards_to_remove=}, {card=}, {self.num_unseen_dealt_cards=}')

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
		assert self.other_player_states, "Cannot call get_num_players before initializing player state"
		return 1 + len(self.other_player_states)

	# Returns copy with all the same public info - but hand is secret
	def get_public_copy(self):
		self_copy = copy.copy(self)
		assert self_copy.plate is self.plate
		self_copy.hand = None
		return self_copy

	def play_card(self, card: Card):
		self._play_card(card)
		self.play_history.append(card)

	def play_chopsticks(self, card1: Card, card2: Card):

		if len(self.hand) < 2:
			raise ValueError('Cannot play chopsticks, only 1 card left in hand')

		try:
			self.plate.remove(Card.Chopsticks)
		except ValueError as ex:
			raise ValueError('No chopsticks on plate, cannot play 2 cards!') from ex

		self._play_card(card1)
		self._play_card(card2)
		self.hand.append(Card.Chopsticks)
		self.play_history.append((card1, card2))

	def _play_card(self, card: Card):
		if card not in self.hand:
			raise ValueError('Cannot play card %s, not in hand: %s' % (card, self.hand))

		self.hand.remove(card)

		# Have to still add to plate
		self.plate.append(card)

		if card == Card.Pudding:
			self.num_pudding += 1

	def end_round(self, round_score):
		self.total_score += round_score
		self.plate = []
		self.play_history = []

	def update_other_player_state_before_pass(self, verbose=False):

		assert self.other_player_states, "Cannot call update_other_player_state_before_pass before initializing player state"

		# DEBUG
		if True and verbose:
			print('%s state before update:' % self.name)
			print(repr(self))
			print()

		# Remove last played card from knowledge of hands

		for state in self.other_player_states:
			last_played_card = state.play_history[-1]

			chopstick_extra_card = None
			if isinstance(last_played_card, tuple):
				assert len(last_played_card) == 2
				last_played_card, chopstick_extra_card = last_played_card

			assert isinstance(last_played_card, Card)
			assert (chopstick_extra_card is None) or isinstance(chopstick_extra_card, Card)

			# TODO: if player with unknown hand used chopsticks, now we know chopsticks are in this hand
			# However, right now the logic here assumes we know either all or none of a hand; this would break that assumption

			if state.hand:
				if last_played_card not in state.hand:
					raise AssertionError(f'Card not in hand: {last_played_card=}, {state.hand=}')
				state.hand.remove(last_played_card)
				if chopstick_extra_card is not None:
					if chopstick_extra_card not in state.hand:
						raise AssertionError(f'Card not in hand: {chopstick_extra_card=}, {state.hand=}')
					state.hand.remove(chopstick_extra_card)
					state.hand.append(Card.Chopsticks)
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

	def __repr__(self) -> str:

		s = 'PlayerState(\n'
		s += f'  name={self.name},\n'
		s += f'  plate={card_names(self.plate, sort=False)},\n'
		s += f'  play_history={card_names(self.play_history, sort=False)},\n'
		s += f'  hand={card_names(self.hand, sort=False)},\n'
		s += f'  total_score={self.total_score},\n'
		s += f'  num_pudding={self.num_pudding},\n'

		if self.other_player_states:
			s += '  other_player_states=[\n'
			for state in (self.other_player_states if self.other_player_states is not None else []):
				s += "    %s: plate %s, hand %s, pudding %i, score %i,\n" % (
					state.name,
					card_names(state.plate, sort=False),
					card_names(state.hand, sort=False),
					state.num_pudding,
					state.total_score)
			s += '  ],\n'
		else:
			s += '  other_player_states=[],\n'

		s += f"  deck_dist={dict_card_names(self.deck_dist)},\n"
		s += f"  num_unseen_dealt_cards={self.num_unseen_dealt_cards},\n"

		s += ')'

		return s


def init_other_player_states(players, forward=True, omniscient=False, verbose=True):

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
		elif verbose:
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
