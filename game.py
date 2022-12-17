#!/usr/bin/env python

from collections.abc import Sequence
from copy import copy
from typing import Callable, Iterable, Optional, Sequence, Union

from ai import AI
from cards import card_names
from deck import Deck, get_deck_distribution
from player import PlayerState, pass_hands, init_other_player_states
from simpleai import SimpleAI
import scoring


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
			ai: Optional[Iterable[AI]] = None,
			):
	
		self.num_players = num_players
		self.num_rounds = num_rounds

		self.num_cards_per_player = num_cards_per_player or get_num_cards_per_player(num_players)

		if not deck_dist:
			deck_dist = get_deck_distribution()

		print('Creating & shuffling deck')

		self.deck = Deck(deck_dist)

		print('Creating player')
		self.player_states = [PlayerState(deck_dist) for _ in range(num_players)]

		if ai is None:
			print('Creating default AI')
			self.ai = [SimpleAI() for _ in range(num_players)]
		elif isinstance(ai, Sequence):
			if len(ai) != num_players:
				raise ValueError('Number of AI must match number of players')
			self.ai = ai

		self.omniscient = omniscient

	def play(self):
		print("Players: " + ", ".join([player.name for player in self.player_states]))
		print()

		print('Starting game')
		print()

		for round_num in range(self.num_rounds):
			pass_forward = (round_num % 2 == 0)

			if self.num_rounds > 1:
				print('==== Round %i =====' % (round_num+1))

			hands = self.deck.deal_hands(self.num_players, self.num_cards_per_player)

			print("Dealing hands:")
			for player, hand in zip(self.player_states, hands):
				player.assign_hand(hand)
				print("\t%s: %s" % (player.name, card_names(player.hand)))
			print()

			init_other_player_states(self.player_states, forward=pass_forward, omniscient=self.omniscient)

			for turn in range(self.num_cards_per_player):
				print('--- Turn %i ---' % (turn+1))
				print()
				self._play_turn(pass_forward=pass_forward)

			scoring.score_round(self.player_states, print_it=True)

			print('Scores after round:')
			for player in self.player_states:
				print("\t%s: %i, %i pudding" % (player.name, player.total_score, player.num_pudding))
			print()

		scoring.score_puddings(self.player_states)


	def _play_turn(self, pass_forward: bool):

		for n, (player, ai) in enumerate(zip(self.player_states, self.ai)):

			verbose = (n == 0)

			print(player.name)
			print("Hand: %s" % card_names(player.hand))
			pudding_str = (" (%i pudding)" % player.num_pudding) if player.num_pudding else ""
			print("Plate: %s%s" % (card_names(player.plate, sort=True), pudding_str))

			if verbose:
				print("State:")
				print(repr(player))

			card = ai.play_turn(player, player.hand, verbose=verbose)

			player.play_card(card)
			print(f"Plays: {card}")
			print()

		debug_update_player_state_verbose = False

		for idx, player in enumerate(self.player_states):
			verbose = debug_update_player_state_verbose and (idx == 0)
			player.update_other_player_state_before_pass(verbose=verbose)

		print('Passing cards %s' % ('forward' if pass_forward else 'backward'))
		pass_hands(self.player_states, forward=pass_forward)

		for idx, player in enumerate(self.player_states):
			verbose = debug_update_player_state_verbose and (idx == 0)
			player.update_other_player_state_after_pass(verbose=verbose)
