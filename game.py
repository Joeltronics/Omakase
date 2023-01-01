#!/usr/bin/env python

from collections import Counter
from collections.abc import Sequence
from copy import copy, deepcopy
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Union

from cards import Card, Pick, card_names
from deck import Deck, get_deck_distribution
from player import CommonGameState, PlayerInterface, PlayerState, init_other_player_states_after_dealing_hands, pass_hands
from tunnel_vision_ai import TunnelVisionAI
import scoring
from utils import add_numbers_to_duplicate_names


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
			players: Optional[Iterable[PlayerInterface]] = None,
			player_names: Optional[Iterable[str]] = None,
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

		if players is None:
			self._print('Creating default AI')
			self._players = [TunnelVisionAI() for _ in range(num_players)]
		elif isinstance(players, Sequence):
			if len(players) != num_players:
				raise ValueError('Number of AI must match number of players')
			self._players = players

		if player_names is None:
			player_names = [p.get_name() for p in self._players]
		elif len(player_names) != num_players:
			raise ValueError('Number of player names must match number of players')

		player_names = add_numbers_to_duplicate_names(player_names)
		assert len(player_names) == len(set(player_names))

		common_game_state = CommonGameState(
			deck_count=sum(deck_dist.values()),
			starting_deck_distribution=deck_dist,
			num_players=num_players,
			num_rounds=num_rounds,
			round_idx=0,
			num_cards_per_player_per_round=self._num_cards_per_player,
			round_pass_forward=True,
			show_hands=omniscient,
		)

		self._print('Creating players')
		self._player_states = [PlayerState(common_game_state=common_game_state, name=name) for name in player_names]
		self._public_states_dict = {p.name: p.public_state for p in self._player_states}

		assert len(self._player_states) == len(set([p.name for p in self._player_states])), "Player names should be guaranteed unique at this point"

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

		for round_idx in range(self._num_rounds):
			round_pass_forward = (round_idx % 2 == 0)

			if self._num_rounds > 1:
				self._print('==== Round %i/%i =====' % (round_idx+1, self._num_rounds))

			hands = self._deck.deal_hands(self._num_players, self._num_cards_per_player)

			self._print("Dealing hands:")
			for player, hand in zip(self._player_states, hands):
				player.assign_hand(hand)
				self._print("\t%s: %s" % (player.name, card_names(player.hand)))
			self._print()

			init_other_player_states_after_dealing_hands(
				self._player_states, round_idx=round_idx, round_pass_forward=round_pass_forward, verbose=self.verbose)

			for turn_idx in range(self._num_cards_per_player):
				if self._num_rounds > 1:
					self._print('--- Round %i/%i, Turn %i/%i ---' % (round_idx + 1, self._num_rounds, turn_idx + 1, self._num_cards_per_player))
				else:
					self._print('--- Turn %i/%i ---' % (turn_idx + 1, self._num_cards_per_player))
				self._print()
				self._play_turn(pass_forward=round_pass_forward)
				self._pause()

			scoring.score_round_players(self._player_states, print_it=self.verbose)

			self._print('Scores after round:')
			for player in self._player_states:
				self._print("\t%s: %i, %i pudding" % (player.name, player.total_score, player.num_pudding))
			self._print()

			self._pause()

		scoring.score_player_puddings(self._player_states, print_it=self.verbose)

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

		for n, (state, player) in enumerate(zip(self._player_states, self._players)):

			verbose = self.verbose and (n == 0)

			self._print(state.name)
			pudding_str = (" (%i pudding)" % state.num_pudding) if state.num_pudding else ""
			self._print("Plate: %s%s" % (card_names(state.plate, sort=True), pudding_str))
			self._print("Hand: %s" % card_names(state.hand))

			if verbose:
				self._print("State:")
				self._print(state.dump())

			# TODO: dump full state if this or state.play_turn() throws an exception
			pick = player.play_turn(deepcopy(state), verbose=verbose)

			self._print(f"Plays: {pick}")

			if isinstance(pick, Card):
				# TODO: log a warning
				pick = Pick(pick)

			if not isinstance(pick, Pick):
				raise ValueError(f'AI played invalid: {pick!r}')

			state.play_turn(pick)

			self._print()

		debug_update_player_state_verbose = False

		for idx, player in enumerate(self._player_states):
			verbose = debug_update_player_state_verbose and (idx == 0)
			player.update_other_player_state_before_pass(self._public_states_dict, verbose=verbose)

		self._print('Passing cards %s' % ('forward' if pass_forward else 'backward'))
		pass_hands(self._player_states, forward=pass_forward)

		for idx, player in enumerate(self._player_states):
			verbose = debug_update_player_state_verbose and (idx == 0)
			player.update_other_player_state_after_pass(verbose=verbose)
