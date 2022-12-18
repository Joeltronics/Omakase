#!/usr/bin/env python

from collections.abc import Collection
from typing import Tuple, Union

from ai import AI
from player import PlayerState
from cards import Card, card_names
from utils import *
import random


def _sashimi_avg_pts(num_cards_in_hand: int, player_state: PlayerState) -> int:
	assert num_cards_in_hand > 0

	n_sashimi_needed = 3 - (count_card(player_state.plate, Card.Sashimi) % 3)

	if n_sashimi_needed > num_cards_in_hand:
		return 0

	if n_sashimi_needed == 1:
		# If this one completes a set, then this is straight-up 10 points,
		# no further calculations needed
		return 10

	elif n_sashimi_needed == 2:
		# TODO: better estimate to account for future (via num_cards_in_hand)
		# What are the odds we will see 1 more?
		# 14/108 cards are Sashimi = 13%
		# Actual odds are (10 * odds of seeing another) - (average value of 1 more card)
		return 6

	elif n_sashimi_needed == 3:
		# TODO: better estimate to account for future (via num_cards_in_hand)
		# What are the odds we will see 2 more? (on 2 separate hands)
		# 14/108 cards are Sashimi = 13%
		return 3


def _tempura_avg_pts(num_cards_in_hand: int, player_state: PlayerState) -> int:
	assert num_cards_in_hand > 0

	n_tempura_needed = 2 - (count_card(player_state.plate, Card.Sashimi) % 2)

	if n_tempura_needed > num_cards_in_hand:
		return 0

	if n_tempura_needed == 1:
		return 5

	elif n_tempura_needed == 2:
		# TODO: better estimate to account for future (via num_cards_in_hand)
		# What are the odds we will see 1 more?
		return 2


def _dumpling_avg_pts(player_state: PlayerState) -> int:
	n_dumpling = count_card(player_state.plate, Card.Dumpling)

	# If already 5 dumplings, there's no point taking any more
	if n_dumpling >= 5:
		return 0

	# TODO: account for possible future dumplings (via num_cards_in_hand)
	return n_dumpling + 1


def _pudding_avg_pts(player_state: PlayerState) -> float:
	if player_state.get_num_players() > 2:
		# 12 points total, across 3 rounds
		return 4 / player_state.get_num_players()
	else:
		# In 2-player, there's no -6, so 6 points total
		return 2 / player_state.get_num_players()


"""
Simple AI that just tries to maximize points in the moment
The only future factor it keeps in mind is how many cards are left
doesn't look ahead at future moves
doesn't look at other players' hands/plates, or what other cards are still out there
"""
class SimpleAI(AI):
	@staticmethod
	def play_turn(player_state: PlayerState, hand: Collection[Card], verbose=False) -> Union[Card, Tuple[Card, Card]]:
		n_cards = len(hand)
		assert n_cards > 0

		if n_cards == 1:
			return hand[0]

		can_use_chopsticks = Card.Chopsticks in player_state.plate and len(hand) >= 2

		wasabi = player_state.get_num_unused_wasabi() > 0

		avg_points = {
			Card.Sashimi: _sashimi_avg_pts(n_cards, player_state),
			Card.Tempura: _tempura_avg_pts(n_cards, player_state),
			Card.Dumpling: _dumpling_avg_pts(player_state),
			Card.SquidNigiri: 9 if wasabi else 3,
			Card.SalmonNigiri: 6 if wasabi else 2,
			Card.EggNigiri: 3 if wasabi else 1,  # TODO: might want to save wasabi for something better?
			Card.Wasabi: min(((n_cards - 1) / 2, 6)),
			Card.Maki3: 4.5 / player_state.get_num_players(),
			Card.Maki2: 3.0 / player_state.get_num_players(),
			Card.Maki1: 1.5 / player_state.get_num_players(),
			Card.Pudding: _pudding_avg_pts(player_state),
			Card.Chopsticks: 0,  # TODO
		}

		# Pick highest point value card - if tied, then at random from max
		max_points = max([avg_points[card] for card in hand])
		possible_picks = [card for card in hand if avg_points[card] == max_points]

		if verbose:
			print_list = [card for card in set(hand)]
			print_list = sorted(print_list, key=(lambda card: avg_points[card]), reverse=True)
			print_list = [(str(card), avg_points[card]) for card in print_list]
			print_list = ["%s: %.1f" % card for card in print_list]
			print_list = ", ".join(print_list)

			if len(possible_picks) > 1:
				print('Point values: [%s], picking randomly from: %s' % (print_list, card_names(possible_picks)))
			else:
				print('Point values: [%s], picking highest: %s' % (print_list, possible_picks[0]))

		return random.choice(possible_picks)
