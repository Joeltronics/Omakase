#!/usr/bin/env python

from collections import Counter
from collections.abc import Sequence
from copy import copy, deepcopy
from dataclasses import dataclass, field
import random
from typing import Optional, List, Iterable, Union

from utils import *
from cards import Card, Pick, sort_cards, card_names, dict_card_names

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


@dataclass
class PublicPlayerState:
	name: str
	plate: list[Card] = field(default_factory=list)
	play_history: list[Pick] = field(default_factory=list)  # History of cards played this round (would be identical to self.plate without chopsticks/pudding)
	total_score: int = 0
	num_pudding: int = 0

	hand: Optional[list[Card]] = None


class PlayerState:
	def __init__(self, deck_dist: dict, name='', show_hand=False):

		# Public info

		if not name:
			name = get_player_name()
		
		self.public_state = PublicPlayerState(name=name)
		self.plate = self.public_state.plate
		self.play_history = self.public_state.play_history

		# Knowledge of deck and other players' state
		self.deck_dist = deepcopy(deck_dist)
		self.other_player_states: List[PublicPlayerState] = []
		self.num_unseen_dealt_cards = 0

		# Private info
		self.hand: Optional[List] = None
		self.passing_hand = None

		self.show_hand = show_hand

	@property
	def name(self) -> str:
		return self.public_state.name

	@property
	def total_score(self) -> int:
		return self.public_state.total_score

	@property
	def num_pudding(self) -> int:
		return self.public_state.num_pudding

	def assign_hand(self, hand):
		# Sorting not actually necessary, but helps print formatting
		self.hand = sort_cards(hand)

		if self.show_hand:
			self.public_state.hand = self.hand

	def update_deck_dist(self, cards_to_remove: Union[Card, Iterable[Card], Counter[Card]], previously_unseen=True):

		def remove(card: Card, num=1):
			assert num > 0

			if self.deck_dist[card] < num:
				raise AssertionError(f'Cannot remove card from deck, already empty; {cards_to_remove=}, {card=}, {num=}, deck_dist={dict_card_names(self.deck_dist)}')

			if previously_unseen and self.num_unseen_dealt_cards < num:
				raise AssertionError(f'All cards are seen, but trying to remove cards from deck distribution; {cards_to_remove=}, {card=}, {num=}, {self.num_unseen_dealt_cards=}')

			self.deck_dist[card] -= num
			if previously_unseen:
				self.num_unseen_dealt_cards -= num

		if isinstance(cards_to_remove, Card):
			remove(cards_to_remove)

		elif isinstance(cards_to_remove, Counter):
			for card, count in cards_to_remove.items():
				remove(card, count)
		else:
			# This would also get triggered by case in remove_one, but this way we'll give a better error message
			if previously_unseen and len(cards_to_remove) > self.num_unseen_dealt_cards:
				raise AssertionError("Trying to remove %i cards from deck dist when only %i unseen cards left"
					% (len(cards_to_remove), self.num_unseen_dealt_cards))

			for card_to_remove in cards_to_remove:
				# Not going with recursive here will break using this on lists of lists,
				# but you probably shouldn't be using it that way anyway
				remove(card_to_remove)

	def get_num_players(self):
		assert self.other_player_states, "Cannot call get_num_players before initializing player state"
		return 1 + len(self.other_player_states)

	def play_turn(self, pick: Pick):
		if len(pick) == 2:
			self._play_chopsticks(pick[0], pick[1])
		else:
			card = pick[0]
			self._play_card(card)
		self.play_history.append(pick)

	def _play_chopsticks(self, card1: Card, card2: Card):

		if len(self.hand) < 2:
			raise ValueError('Cannot play chopsticks, only 1 card left in hand')

		try:
			self.plate.remove(Card.Chopsticks)
		except ValueError as ex:
			raise ValueError('No chopsticks on plate, cannot play 2 cards!') from ex

		self._play_card(card1)
		self._play_card(card2)
		self.hand.append(Card.Chopsticks)

	def _play_card(self, card: Card):

		assert isinstance(card, Card)

		if card not in self.hand:
			raise ValueError(f'Cannot play card {card}, not in hand: {self.hand}')

		self.hand.remove(card)

		# Have to still add to plate
		# TODO: don't put puddings on plate
		self.plate.append(card)

		if card == Card.Pudding:
			self.public_state.num_pudding += 1

	def end_round(self, round_score: int):
		self.public_state.total_score += round_score
		self.plate.clear()
		self.play_history.clear()

	def score_puddings(self, pudding_score: int):
		self.public_state.total_score += pudding_score

	def update_other_player_state_before_pass(self, players: dict[str, PublicPlayerState], verbose=False):

		assert self.other_player_states, "Cannot call update_other_player_state_before_pass before initializing player state"

		# DEBUG
		# TODO: use logging library for this
		if True and verbose:
			print('%s state before update:' % self.name)
			print(repr(self))
			print()

		# Update plate, play history, and knowledge of hands & deck distribution

		for state in self.other_player_states:
			new_state = players[state.name]

			state.plate = deepcopy(new_state.plate)
			state.play_history = deepcopy(new_state.play_history)

			last_play = state.play_history[-1]

			assert state.hand

			for card in last_play:
				if card in state.hand:
					state.hand.remove(card)
				elif Card.Unknown in state.hand:
					self.update_deck_dist(card)
					state.hand.remove(Card.Unknown)
				else:
					raise AssertionError(f'Player {state.name} played card not in hand: {last_play=}, hand={card_names(state.hand)}')

			if len(last_play) > 1:
				state.hand.append(Card.Chopsticks)

		# DEBUG
		if True and verbose:
			print('%s state after removing, before shift:' % self.name)
			print(repr(self))
			print()

		assert self.passing_hand is None
		self.passing_hand = copy(self.hand)

	def update_other_player_state_after_pass(self, verbose=False):

		assert self.passing_hand is not None

		passed_hand = self.other_player_states[-1].hand

		num_other_players = len(self.other_player_states)
		for idx in reversed(range(num_other_players-1)):
			self.other_player_states[idx + 1].hand = self.other_player_states[idx].hand
		self.other_player_states[0].hand = self.passing_hand

		self.passing_hand = None

		if verbose:
			print('%s state:' % self.name)
			print(repr(self))
			print()

		# Compare passed_hand with self.hand
		# These should be the same, except for cards that were previously unknown
		assert len(passed_hand) == len(self.hand)
		assert Card.Unknown not in self.hand
		hand_before_seeing = Counter(passed_hand)
		hand_after_seeing = Counter(self.hand)

		if Card.Unknown in hand_before_seeing:
			hand_before_seeing.pop(Card.Unknown)
			newly_seen_cards = hand_after_seeing - hand_before_seeing
			assert Card.Unknown not in newly_seen_cards
			self.update_deck_dist(newly_seen_cards)
		elif hand_before_seeing != hand_after_seeing:
			raise AssertionError(f"Received hand that doesn't match expected (expected: {card_names(passed_hand)}, received: {card_names(self.hand)})")

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
				assert state is not None
				s += "    %s: plate %s, hand %s, pudding %i, score %i,\n" % (
					state.name,
					card_names(state.plate, sort=False),
					None if state.hand is None else card_names(state.hand, sort=False),
					state.num_pudding,
					state.total_score)
			s += '  ],\n'
		else:
			s += '  other_player_states=[],\n'

		s += f"  deck_dist={dict_card_names(self.deck_dist)},\n"
		s += f"  num_unseen_dealt_cards={self.num_unseen_dealt_cards},\n"

		s += ')'

		return s

	def dump(self) -> str:
		"""like __repr__ but formatted a bit more human-friendly"""

		s = ''

		s += f'PlayerState for {self.name}:\n'
		s += '\n'

		public_states = [self.public_state] + self.other_player_states

		sep = ' | '
		eol = ' |\n'

		s += f'{"Name:":<10}' + sep + sep.join([f'{s.name:^20}' for s in public_states]) + eol
		s += f'{"Score:":<10}' + sep + sep.join([f'{s.total_score:>20}' for s in public_states]) + eol
		s += f'{"Pudding:":<10}' + sep + sep.join([f'{s.num_pudding:>20}' for s in public_states]) + eol

		# Plates may have different length due to puddings
		max_plate_len = max(len(s.plate) for s in public_states)

		if max_plate_len:
			s += 'Plate:\n'
			for idx in range(max_plate_len):
				s += f'{"":10}' + sep + sep.join([
					f'{s.plate[idx]:20}' if idx <= len(s.plate) else ' ' * 20
					for s in public_states
				]) + eol
		else:
			s += 'Plate: [all empty]\n'

		# TODO: show current plate score

		# TODO: show play history?

		num_cards_in_hand = len(self.hand)
		if num_cards_in_hand:
			hands = [self.hand] + [s.hand for s in self.other_player_states]
			assert all(len(h) == num_cards_in_hand for h in hands)
			s += 'Hand:\n'
			for idx in range(num_cards_in_hand):
				s += f'{"":10}' + sep + sep.join([f'{h[idx]:20}' for h in hands]) + eol
		else:
			s += 'Hand: [all empty]\n'

		s += '\n'
		s += f'Num unseen dealt cards: {self.num_unseen_dealt_cards}\n'
		s += f'Unseen: {dict_card_names(self.deck_dist)}\n'

		return s


def init_other_player_states_after_dealing_hands(players: Sequence[PlayerState], round_pass_forward=True, verbose=True):

	players_list = players if round_pass_forward else list(reversed(players))

	assert all(p.hand for p in players), "Must assign hands before calling init_other_player_states_after_dealing_hands"

	hand_num_cards = len(players[0].hand)
	assert all(len(p.hand) == hand_num_cards for p in players), "All player hands must be the same size!"

	assert all(p.num_unseen_dealt_cards == 0 for p in players), "num_unseen_dealt_cards nonzero at start"

	num_players = len(players)
	for this_player_idx, player in enumerate(players_list):

		player.other_player_states = []

		for other_player_rel_idx in range(num_players-1):
			# Start with player after the current one
			other_player_true_idx = (this_player_idx + other_player_rel_idx + 1) % num_players
			other_player = players_list[other_player_true_idx]
			player.other_player_states.append(deepcopy(other_player.public_state))

		assert len(player.other_player_states) == num_players - 1

		assert player.num_unseen_dealt_cards == 0
		player.update_deck_dist(player.hand, previously_unseen=False)
		assert player.num_unseen_dealt_cards == 0

		for player_public_state in player.other_player_states:
			if player_public_state.hand is not None:
				player.update_deck_dist(player_public_state.hand, previously_unseen=False)
			else:
				player_public_state.hand = [Card.Unknown] * hand_num_cards
				player.num_unseen_dealt_cards += hand_num_cards

		if verbose and player.num_unseen_dealt_cards:
			print("%s, %i unseen cards" % (player.name, player.num_unseen_dealt_cards))


def pass_hands(players: Sequence[PlayerState], forward=True):
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
	

class PlayerInterface:
	def get_name(self) -> str:
		raise NotImplementedError('To be implemented by the child class!')

	def play_turn(
			self,
			player_state: PlayerState,
			hand: Collection[Card],
			verbose=False,
			) -> Pick:
		"""
		:returns: card to play, or 2 cards if playing chopsticks (must have chopsticks on plate)
		"""
		raise NotImplementedError('To be implemented by the child class!')
