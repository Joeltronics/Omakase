#!/usr/bin/env python

from collections.abc import Collection
import random
from typing import Union, Tuple

from player import PlayerState
from cards import Card, card_names
from utils import *


class AI:
	def play_turn(
			self,
			player_state: PlayerState,
			hand: Collection[Card],
			verbose=False,
			) -> Union[Card, Tuple[Card, Card]]:
		raise NotImplementedError('To be implemented by the child class!')


class RandomAI(AI):
	@staticmethod
	def play_turn(player_state: PlayerState, hand: Collection[Card], verbose=False) -> Union[Card, Tuple[Card, Card]]:
		"""
		:returns: card to play, or 2 cards if playing chopsticks (must have chopsticks on plate)
		"""
		assert len(hand) > 0

		can_use_chopsticks = Card.Chopsticks in player_state.plate and len(hand) >= 2
		use_chopsticks = can_use_chopsticks and bool(random.getrandbits(1))

		if use_chopsticks:
			ret = random.sample(hand, 2)
			assert len(ret) == 2
			return ret[0], ret[1]
		else:
			return random.choice(hand)


# A very simple AI that's mostly random, but makes a few obvious choices:
#   Don't pick card that's straight-up worse than another (e.g. maki1 when maki3 is available)
#   Always use chopsticks on 2nd last turn (if there's a point)
#   Don't take chopsticks on 2nd last turn
#   Complete a set if possible
#   Don't take sets that will be impossible to complete (based only on number of cards left - doesn't keep track of other hands)
#   Take a squid if we have a wasabi out
#   Don't take more than 5 dumplings
class RandomPlusAI(AI):
	@staticmethod
	def play_turn(player_state: PlayerState, hand: Collection[Card], verbose=False) -> Union[Card, Tuple[Card, Card]]:
		n_cards = len(hand)
		assert n_cards > 0
		hand_maybes = set(hand)

		can_use_chopsticks = Card.Chopsticks in player_state.plate and len(hand) >= 2

		# TODO: maybe use chopsticks

		if n_cards <= 2:
			hand_maybes.discard(Card.Chopsticks)

		if Card.Maki3 in hand_maybes:
			hand_maybes.discard(Card.Maki2)
			hand_maybes.discard(Card.Maki1)
		elif Card.Maki2 in hand_maybes:
			hand_maybes.discard(Card.Maki1)

		if Card.SquidNigiri in hand_maybes:
			hand_maybes.discard(Card.SalmonNigiri)
			hand_maybes.discard(Card.EggNigiri)
		elif Card.SalmonNigiri in hand_maybes:
			hand_maybes.discard(Card.EggNigiri)

		if Card.Sashimi in hand_maybes:
			n_sashimi_needed = 3 - (count_card(player_state.plate, Card.Sashimi) % 3)
			if n_sashimi_needed == 1:
				# Definitely take sashimi
				return Card.Sashimi
			elif n_sashimi_needed > n_cards:
				# If it's not physically possibly to score this, don't take it
				hand_maybes.discard(Card.Sashimi)

		if player_state.get_num_unused_wasabi() > 0 and Card.SquidNigiri in hand_maybes:
			return Card.SquidNigiri

		if Card.Tempura in hand_maybes:
			n_tempura_needed = 2 - (count_card(player_state.plate, Card.Sashimi) % 2)
			if n_tempura_needed == 1:
				return Card.Tempura
			elif n_tempura_needed > n_cards:
				# If it's not physically possibly to score this, don't take it
				hand_maybes.discard(Card.Tempura)

		if count_card(player_state.plate, Card.Dumpling) >= 5:
			hand_maybes.discard(Card.Dumpling)

		# Pick a card at random from the ones that are left

		if len(hand_maybes) >= 1:
			hand_maybes = list(hand_maybes)
			if verbose:
				print('Selecting randomly from: %s' % card_names(hand_maybes))
			return random.choice(hand_maybes)
		else:
			# womp womp
			if verbose:
				print('No good options, selecting at random')
			return random.choice(hand)


"""
old code:

def pick_card(players, currPlayerIdx):

	currPlayer = players[currPlayerIdx]
	otherPlayers = players[:currPlayerIdx] + players[currPlayerIdx+1:]

	# Figure out current plate state:

	nPlateWasabi = 0
	nPlateTempura = 0
	nPlateSashimi = 0
	nPlateDumplings = 0

	for card in currPlayer.plate:
		if card in [Cards.EggNigiri, Cards.SalmonNigiri, Cards.SquidNigiri]:
			if nPlateWasabi > 0:
				nPlateWasabi -= 1
		elif card is Cards.Wasabi:
			nPlateWasabi += 1
		elif card is Cards.Dumpling:
			nPlateDumplings += 1
		elif card is Cards.Tempura:
			nPlateTempura += 1
		elif card is Cards.Sashimi:
			nPlateSashimi += 1

	nRemainingSashimi = 0
	nRemainingTempura = 0
	nRemainingDumplings = 0

	for p in players:
		hand = p.hand
		# TODO: figure out how many more times we will see this hand
		for card in hand:
			if card is Cards.Dumpling:
				nRemainingDumplings += 1
			elif card is Cards.Tempura:
				nRemainingTempura += 1
			elif card is Cards.Sashimi:
				nRemainingSashimi += 1

	pass
"""

