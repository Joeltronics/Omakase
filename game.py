#!/usr/bin/env python

from copy import copy, deepcopy
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Union

from ai import AI
from cards import Card, card_names
from deck import Deck, get_deck_distribution
from player import PlayerState, pass_hands, init_other_player_states
from tunnel_vision_ai import TunnelVisionAi
import scoring


@dataclass(frozen=True)
class PlayerResult:
	name: str
	rank: int
	score: int
	num_puddings: int


def get_num_cards_per_player(num_players: int) -> int:
	try:
		return {
			2: 10,
			3: 9,
			4: 8,
			5: 7
		}[num_players]
	except KeyError:
		raise ValueError(f'Invalid number of players: {num_players}') from None


class Game:
	def __init__(
			self,
			num_players=4,
			num_rounds=3,
			deck_dist=None,
			num_cards_per_player=None,
			omniscient=False,
			player_names: Optional[Iterable[str]] = None,
			ai: Optional[Iterable[AI]] = None,
			verbose: bool = False,
			pause_after_turn: bool = False,
			):

		self.verbose = verbose
		self.pause_after_turn = pause_after_turn

		self._num_players = num_players
		self._num_rounds = num_rounds

		self._num_cards_per_player = num_cards_per_player or get_num_cards_per_player(num_players)

		if not deck_dist:
			deck_dist = get_deck_distribution()

		self._print('Creating & shuffling deck')

		self._deck = Deck(deck_dist)

		if player_names is None:
			player_names = [None] * num_players
		elif len(player_names) != num_players:
			raise ValueError('Number of player names must match number of players')

		self._print('Creating players')
		self._player_states = [PlayerState(deck_dist, name=name) for name in player_names]

		if ai is None:
			self._print('Creating default AI')
			self._ai = [TunnelVisionAi() for _ in range(num_players)]
		elif isinstance(ai, Sequence):
			if len(ai) != num_players:
				raise ValueError('Number of AI must match number of players')
			self._ai = ai

		self._omniscient = omniscient

	def _print(self, *args, **kwargs):
		if self.verbose:
			print(*args, **kwargs)

	def _pause(self):
		if not self.pause_after_turn:
			return
		input('Press enter to continue...')

	def play(self) -> Iterable[PlayerResult]:
		self._print("Players: " + ", ".join([player.name for player in self._player_states]))
		self._print()

		self._print('Starting game')
		self._print()

		for round_num in range(self._num_rounds):
			pass_forward = (round_num % 2 == 0)

			if self._num_rounds > 1:
				self._print('==== Round %i =====' % (round_num+1))

			hands = self._deck.deal_hands(self._num_players, self._num_cards_per_player)

			self._print("Dealing hands:")
			for player, hand in zip(self._player_states, hands):
				player.assign_hand(hand)
				self._print("\t%s: %s" % (player.name, card_names(player.hand)))
			self._print()

			init_other_player_states(self._player_states, forward=pass_forward, omniscient=self._omniscient, verbose=self.verbose)

			for turn in range(self._num_cards_per_player):
				self._print('--- Turn %i/%i ---' % (turn+1, self._num_cards_per_player))
				self._print()
				self._play_turn(pass_forward=pass_forward)
				self._pause()

			scoring.score_round(self._player_states, print_it=self.verbose)

			self._print('Scores after round:')
			for player in self._player_states:
				self._print("\t%s: %i, %i pudding" % (player.name, player.total_score, player.num_pudding))
			self._print()

			self._pause()

		scoring.score_puddings(self._player_states, print_it=self.verbose)

		names =         [s.name        for s in self._player_states]
		scores =        [s.total_score for s in self._player_states]
		nums_puddings = [s.num_pudding for s in self._player_states]
		ranks = scoring.rank_players(self._player_states, print_it=self.verbose)

		return [
			PlayerResult(name=name, rank=rank, score=score, num_puddings=num_puddings)
			for name, rank, score, num_puddings
			in zip(names, ranks, scores, nums_puddings)
		]

	def _play_turn(self, pass_forward: bool):

		for n, (player, ai) in enumerate(zip(self._player_states, self._ai)):

			verbose = self.verbose and (n == 0)

			self._print(player.name)
			pudding_str = (" (%i pudding)" % player.num_pudding) if player.num_pudding else ""
			self._print("Plate: %s%s" % (card_names(player.plate, sort=True), pudding_str))
			self._print("Hand: %s" % card_names(player.hand))

			if verbose:
				self._print("State:")
				self._print(repr(player))

			card_or_pair = ai.play_turn(deepcopy(player), copy(player.hand), verbose=verbose)

			if isinstance(card_or_pair, Card):
				player.play_card(card_or_pair)
				self._print(f"Plays: {card_or_pair}")
			elif isinstance(card_or_pair, tuple) and len(card_or_pair) == 2:
				player.play_chopsticks(*card_or_pair)
				self._print(f"Plays chopsticks: {card_or_pair[0]} + {card_or_pair[1]}")
			else:
				raise ValueError(f'AI played invalid: {card_or_pair!r}')
			self._print()

		debug_update_player_state_verbose = False

		for idx, player in enumerate(self._player_states):
			verbose = debug_update_player_state_verbose and (idx == 0)
			player.update_other_player_state_before_pass(verbose=verbose)

		self._print('Passing cards %s' % ('forward' if pass_forward else 'backward'))
		pass_hands(self._player_states, forward=pass_forward)

		for idx, player in enumerate(self._player_states):
			verbose = debug_update_player_state_verbose and (idx == 0)
			player.update_other_player_state_after_pass(verbose=verbose)
