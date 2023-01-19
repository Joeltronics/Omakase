#!/usr/bin/env python

from collections import Counter, deque
from collections.abc import Collection, MutableSequence, Sequence
from copy import copy, deepcopy
from dataclasses import dataclass, field
from itertools import islice
import random
from typing import Optional, List, Iterable, Union

from utils import *
from cards import Card, Pick, Plate, sort_cards, card_names, dict_card_names

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
class CommonGameState:
	deck_count: int
	starting_deck_distribution: dict
	num_players: int
	num_rounds: int
	round_idx: int
	num_cards_per_player_per_round: int
	round_pass_forward: bool
	show_hands: bool = False

	@property
	def last_round(self) -> bool:
		return self.round_idx == self.num_rounds - 1

	@property
	def total_num_cards_per_round(self) -> int:
		return self.num_players * self.num_cards_per_player_per_round

	@property
	def num_cards_dealt(self) -> int:
		return (self.round_idx + 1) * self.total_num_cards_per_round

	@property
	def num_cards_to_be_dealt(self) -> int:
		num_rounds_remaining = self.num_rounds - (self.round_idx + 1)
		return num_rounds_remaining * self.total_num_cards_per_round

	@property
	def num_cards_remaining_in_deck(self) -> int:
		return self.deck_count - self.num_cards_dealt



@dataclass
class PublicPlayerState:
	name: str
	plate: Plate = field(default_factory=Plate)
	play_history: list[Pick] = field(default_factory=list)  # History of cards played this round
	total_score: int = 0
	num_pudding: int = 0


class PlayerState:
	def __init__(self, common_game_state: CommonGameState, name=''):

		# Public info

		if not name:
			name = get_player_name()

		self.common_game_state = common_game_state

		self.public_state = PublicPlayerState(name=name)
		self.public_states = [self.public_state]

		# Knowledge of deck
		self.deck_dist = deepcopy(self.common_game_state.starting_deck_distribution)  # TODO: rename this to unseen_deck_dist
		self.num_unseen_dealt_cards = 0

		# Knowledge of hands (own and other players')
		self.hands = deque()

	@property
	def hand(self) -> MutableSequence[Card]:
		if not self.hands:
			return []
		return self.hands[0]

	@property
	def other_player_states(self) -> Sequence[PublicPlayerState]:
		return self.public_states[1:]

	@property
	def other_player_hands(self) -> Iterable:
		# TODO: this should be Iterable[MutableCollection[Card]], but MutableCollection does not exist
		return islice(self.hands, 1, None)

	@property
	def name(self) -> str:
		return self.public_state.name

	@property
	def total_score(self) -> int:
		return self.public_state.total_score

	@property
	def num_pudding(self) -> int:
		return self.public_state.num_pudding

	@property
	def any_unknown_cards(self) -> bool:
		return self.num_unseen_dealt_cards > 0

	@property
	def plate(self) -> Plate:
		return self.public_state.plate

	@property
	def play_history(self) -> MutableSequence[Pick]:
		return self.public_state.play_history

	def init_round(
			self,
			hand: Collection[Card],
			other_player_public_states: Sequence[PublicPlayerState],
			other_player_hands: Optional[Sequence[Collection[Card]]] = None,
			):

		# Sort just for sake of print formatting
		hand = sort_cards(hand)

		if self.common_game_state.show_hands:
			if not other_player_hands:
				raise ValueError('Must provide other_player_hands if self.common_game_state.show_hands')
			other_player_hands = [sort_cards(h) for h in other_player_hands]
		else:
			if other_player_hands:
				raise ValueError('Must not provide other_player_hands if not self.common_game_state.show_hands')
			unknown_hand = [Card.Unknown] * len(hand)
			other_player_hands = [deepcopy(unknown_hand) for _ in range(len(other_player_public_states))]

		self.public_states = [self.public_state] + list(other_player_public_states)
		self.hands = deque((hand,)) + deque(other_player_hands)

		# Update unseen card info

		self.num_unseen_dealt_cards = 0
		self.update_deck_dist(self.hand, previously_unseen=False)
		assert self.num_unseen_dealt_cards == 0

		if self.common_game_state.show_hands:
			for other_hand in other_player_hands:
				assert not any(card == Card.Unknown for card in other_hand)
				self.update_deck_dist(other_hand, previously_unseen=False)
		else:
			self.num_unseen_dealt_cards += len(hand) * len(other_player_hands)

		if self.common_game_state.show_hands:
			assert self.num_unseen_dealt_cards == 0

	def update_deck_dist(self, cards_to_remove: Union[Card, Iterable[Card], Counter[Card]], previously_unseen=True):

		def remove(card: Card, num=1):
			assert num > 0

			if card == Card.Unknown:
				return

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
			# This would also get triggered by the case in remove(), but catch it before that for better error message
			if previously_unseen and len(cards_to_remove) > self.num_unseen_dealt_cards:
				raise AssertionError("Trying to remove %i cards from deck dist when only %i unseen cards left"
					% (len(cards_to_remove), self.num_unseen_dealt_cards))

			for card_to_remove in cards_to_remove:
				remove(card_to_remove)

	def get_num_players(self) -> int:
		return self.common_game_state.num_players

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

		if not self.plate.chopsticks:
			raise ValueError('No chopsticks on plate, cannot play 2 cards!')
		self.plate.chopsticks -= 1

		self._play_card(card1)
		self._play_card(card2)
		self.hand.append(Card.Chopsticks)

	def _play_card(self, card: Card):

		assert isinstance(card, Card)

		if card not in self.hand:
			raise ValueError(f'Player "{self.name}" cannot play card {card}, not in hand: {self.hand}')

		self.hand.remove(card)
		self.plate.add(card)

		if card == Card.Pudding:
			self.public_state.num_pudding += 1

	def end_round(self, round_score: int):
		self.public_state.total_score += round_score
		self.plate.clear()
		self.play_history.clear()

	def score_puddings(self, pudding_score: int):
		self.public_state.total_score += pudding_score

	def _observe_other_player_plays(self, verbose=False):

		assert len(self.public_states) > 1, "Cannot call update_other_player_state_before_pass before initializing player state"

		# DEBUG
		# TODO: use logging library for this
		if True and verbose:
			print('%s state before update:' % self.name)
			print(repr(self))
			print()

		# public_states are shared, so we don't have to update those - game will do it
		# But we do need to update our copy of hand
		# TODO Python 3.10: strict=True
		for state, hand in zip(self.other_player_states, self.other_player_hands):

			last_play = state.play_history[-1]

			for card in last_play:
				if card in hand:
					hand.remove(card)
				elif Card.Unknown in hand:
					self.update_deck_dist(card)
					hand.remove(Card.Unknown)
				else:
					raise AssertionError(f'Player {state.name} played card not in hand: {last_play=}, hand={card_names(hand)}')

			if len(last_play) > 1:
				hand.append(Card.Chopsticks)

		# DEBUG
		if True and verbose:
			print('%s state after removing, before shift:' % self.name)
			print(repr(self))
			print()

	def _observe_new_hand(self, old_hand: Sequence[Card], new_hand: Sequence[Card]):

		assert len(new_hand) == len(old_hand)

		hand_before_seeing = Counter(old_hand)
		hand_after_seeing = Counter(new_hand)

		if Card.Unknown in hand_before_seeing:
			hand_before_seeing.pop(Card.Unknown)
			newly_seen_cards = hand_after_seeing - hand_before_seeing
			assert Card.Unknown not in newly_seen_cards
			self.update_deck_dist(newly_seen_cards)
		elif hand_before_seeing != hand_after_seeing:
			raise AssertionError(f"Received hand that doesn't match expected (expected: {card_names(old_hand)}, received: {card_names(new_hand)})")

	def pass_hands(self, new_hand: Sequence[Card]):

		assert Card.Unknown not in new_hand

		self._observe_other_player_plays(verbose=False)

		assert isinstance(self.hands, deque)
		self.hands.rotate(1)

		self._observe_new_hand(self.hands[0], new_hand)

		self.hands[0] = copy(new_hand)

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
			# TODO Python 3.10: strict=True
			for state, hand in zip(self.other_player_states, self.other_player_hands):
				assert state is not None
				s += "    %s: plate %s, hand %s, pudding %i, score %i,\n" % (
					state.name,
					card_names(state.plate, sort=False),
					None if hand is None else card_names(hand, sort=False),
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

		sep = ' | '
		eol = ' |\n'

		s += f'{"Name:":<10}' + sep + sep.join([f'{s.name:^20}' for s in self.public_states]) + eol
		# s += f'{"Score:":<10}' + sep + sep.join([f'{s.total_score:>20}' for s in self.public_states]) + eol
		s += f'{"Score:":<10}' + sep + sep.join([f'{s.total_score + s.plate.score:>20}' for s in self.public_states]) + eol
		s += f'{"Pudding:":<10}' + sep + sep.join([f'{s.num_pudding:>20}' for s in self.public_states]) + eol

		s += 'Plate:\n'
		# s += f'{"Score:":10}' + sep + sep.join([f'{s.plate.score:20}' for s in self.public_states]) + eol

		if any(s.plate.maki for s in self.public_states):
			s += f'{"Maki:":10}' + sep + sep.join([f'{s.plate.maki:20}' for s in self.public_states]) + eol
		if any(s.plate.chopsticks for s in self.public_states):
			s += f'{"Chop:":10}' + sep + sep.join([f'{s.plate.chopsticks:20}' for s in self.public_states]) + eol
		if any(s.plate.unused_wasabi for s in self.public_states):
			s += f'{"Wasabi:":10}' + sep + sep.join([f'{s.plate.unused_wasabi:20}' for s in self.public_states]) + eol
		if any(s.plate.unscored_sashimi for s in self.public_states):
			s += f'{"Sashimi:":10}' + sep + sep.join([f'{s.plate.unscored_sashimi:20}' for s in self.public_states]) + eol
		if any(s.plate.unscored_tempura for s in self.public_states):
			s += f'{"Tempura:":10}' + sep + sep.join([f'{int(s.plate.unscored_tempura):20}' for s in self.public_states]) + eol
		if any(s.plate.dumplings for s in self.public_states):
			s += f'{"Dumplings:":10}' + sep + sep.join([f'{s.plate.dumplings:20}' for s in self.public_states]) + eol

		# TODO: show play history?

		num_cards_in_hand = len(self.hand)
		if num_cards_in_hand:
			assert all(len(h) == num_cards_in_hand for h in self.hands)
			s += 'Hand:\n'
			for idx in range(num_cards_in_hand):
				s += f'{"":10}' + sep + sep.join([f'{h[idx]:20}' for h in self.hands]) + eol
		else:
			s += 'Hand: [all empty]\n'

		s += '\n'
		s += f'Num unseen dealt cards: {self.num_unseen_dealt_cards}\n'
		s += f'Unseen: {dict_card_names(self.deck_dist)}\n'

		return s


def init_round(
		player_states: Sequence[PlayerState],
		hands: Sequence[Collection[Card]],
		round_idx: int,
		round_pass_forward: bool,
		verbose=False,
		):

	hand_num_cards = len(hands[0])
	assert all(len(hand) == hand_num_cards for hand in hands[1:]), "All player hands must be the same size!"

	common_game_state = player_states[0].common_game_state
	assert all(player.common_game_state is common_game_state for player in player_states[1:])

	assert len(player_states) == common_game_state.num_players
	num_players = common_game_state.num_players

	common_game_state.round_idx = round_idx
	common_game_state.round_pass_forward = round_pass_forward

	if not round_pass_forward:
		player_states = list(reversed(player_states))

	if verbose:
		print("Dealing hands:")

	for this_player_idx, (player, hand) in enumerate(zip(player_states, hands)):

		other_player_public_states = [
			player_states[(this_player_idx + rel_idx) % num_players].public_state
			for rel_idx in range(1, num_players)
		]

		if common_game_state.show_hands:
			other_player_hands = [
				copy(hands[(this_player_idx + rel_idx) % num_players])
				for rel_idx in range(1, num_players)
			]
		else:
			other_player_hands = None

		player.init_round(hand, other_player_public_states, other_player_hands=other_player_hands)
		if verbose:
			print("\t%s: %s" % (player.name, card_names(player.hand)))

		assert len(player.public_states) == num_players
		assert len(player.other_player_states) == num_players - 1

		if verbose and player.num_unseen_dealt_cards:
			print("%s, %i unseen cards" % (player.name, player.num_unseen_dealt_cards))

	if verbose:
		print()

	assert all(p.hand for p in player_states)
	assert all(len(p.public_states) == num_players for p in player_states)



class PlayerInterface:
	def get_name(self) -> str:
		raise NotImplementedError('To be implemented by the child class!')

	def play_turn(
			self,
			player_state: PlayerState,
			verbose=False,
			) -> Pick:
		"""
		:returns: card from player_state.hand to play, or 2 cards if playing chopsticks (must have chopsticks on plate)
		"""
		raise NotImplementedError('To be implemented by the child class!')
