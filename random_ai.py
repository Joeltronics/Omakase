#!/usr/bin/env python

from collections import Counter
from collections.abc import Collection, Sequence
from enum import IntEnum, unique
import random
from typing import Union, Tuple

from player import PlayerInterface, PlayerState
from cards import Card, Pick, card_names
from utils import *


class RandomAI(PlayerInterface):
	@staticmethod
	def get_name() -> str:
		return "RandomAI"

	@staticmethod
	def play_turn(player_state: PlayerState, verbose=False) -> Pick:
		hand = player_state.hand
		assert len(hand) > 0

		can_use_chopsticks = Card.Chopsticks in player_state.plate and len(hand) >= 2
		use_chopsticks = can_use_chopsticks and random_bool()

		if use_chopsticks:
			ret = random.sample(hand, 2)
			assert len(ret) == 2
			return Pick(ret[0], ret[1])
		else:
			return Pick(random.choice(hand))


@unique
class _RandomPickState(IntEnum):
	great = 1
	fine = 0
	useless_to_me = -1
	useless_to_anyone = -2


def _random_plus_pick_card(
		plate: Sequence[Card],
		hand: Collection[Card],
		verbose=False,
		take_obvious_picks=True,
		) -> Tuple[Card, _RandomPickState]:

	n_cards = len(hand)
	assert n_cards > 0
	hand_maybes = set(hand)
	fallbacks = set(hand)  # Cards that aren't useful to us, but could at least block someone else

	num_sashimi_needed = get_num_sashimi_needed(plate)
	num_tempura_needed = get_num_tempura_needed(plate)
	num_dumplings = count_card(plate, Card.Dumpling)
	num_chopsticks = count_card(plate, Card.Chopsticks)
	num_unused_wasabi = get_num_unused_wasabi(plate)

	# Handle certain great combos we should always grab if we can

	if take_obvious_picks:
		if num_sashimi_needed == 1 and Card.Sashimi in hand_maybes:
			return Card.Sashimi, _RandomPickState.great  # 10 points

		if num_unused_wasabi and Card.SquidNigiri in hand_maybes:
			return Card.SquidNigiri, _RandomPickState.great  # 9 points

		if num_dumplings == 4 and Card.Dumpling in hand_maybes:
			return Card.Dumpling, _RandomPickState.great  # 6 points

		# if num_unused_wasabi and Card.SalmonNigiri in hand_maybes:
		# 	return Card.SalmonNigiri, _RandomPickState.great  # 6 points

		# if num_tempura_needed == 1 and Card.Tempura in hand_maybes:
		# 	return Card.Tempura, _RandomPickState.great  # 5 points

	# Chopsticks: don't take if can't use

	if n_cards <= 2 + num_chopsticks:
		hand_maybes.discard(Card.Chopsticks)

	# Maki: don't take lower value

	if Card.Maki3 in hand_maybes:
		hand_maybes.discard(Card.Maki2)
		hand_maybes.discard(Card.Maki1)
	elif Card.Maki2 in hand_maybes:
		hand_maybes.discard(Card.Maki1)

	# Wasabi: don't take more wasabi than turns left
	# TODO

	# Nigiri: don't take lower value

	if Card.SquidNigiri in hand_maybes:
		hand_maybes.discard(Card.SalmonNigiri)
		hand_maybes.discard(Card.EggNigiri)
	elif Card.SalmonNigiri in hand_maybes:
		hand_maybes.discard(Card.EggNigiri)

	# Sashimi: don't take if impossible to complete set (based only on number of cards left)

	if num_sashimi_needed > n_cards and Card.Sashimi in hand_maybes:
		hand_maybes.discard(Card.Sashimi)
		fallbacks.add(Card.Sashimi)

	# Tempura: don't take if impossible to complete set (based only on number of cards left)

	if num_tempura_needed > n_cards and Card.Tempura in hand_maybes:
		hand_maybes.discard(Card.Tempura)
		fallbacks.add(Card.Tempura)

	# Dumplings: don't take if already maxed

	if num_dumplings >= 5:
		hand_maybes.discard(Card.Dumpling)
		fallbacks.add(Card.Dumpling)

	# Pick a card at random from the ones that are left

	if hand_maybes:
		hand_maybes = list(hand_maybes)
		if verbose:
			print('Selecting randomly from: %s' % card_names(hand_maybes))
		return random.choice(hand_maybes), _RandomPickState.fine
	elif fallbacks:
		fallbacks = list(fallbacks)
		if verbose:
			print('No good options, selecting randomly from cards that could at least block someone: %s' % card_names(fallbacks))
		return random.choice(fallbacks), _RandomPickState.useless_to_me
	else:
		# womp womp
		if verbose:
			print('No good options nor blocking cards, selecting at random')
		return random.choice(hand), _RandomPickState.useless_to_anyone


def _random_plus_pick_cards(
		player_state: PlayerState,
		take_obvious_picks: bool,
		verbose=False,
		) -> Pick:

	hand = player_state.hand

	if len(hand) == 1:
		return Pick(hand[0])

	plate = player_state.plate

	num_chopsticks = count_card(plate, Card.Chopsticks)

	can_use_chopsticks = num_chopsticks and len(hand) > 1
	should_use_chopsticks = can_use_chopsticks and len(hand) <= (1 + num_chopsticks)

	# First, handle certain obvious picks for pairs of cards, which the individual card picks would miss
	if take_obvious_picks and can_use_chopsticks:
		hand_count = Counter(hand)

		if Card.Sashimi in hand_count and hand_count[Card.Sashimi] >= 2 and get_num_sashimi_needed(plate) == 2:
			return Pick(Card.Sashimi, Card.Sashimi)  # 10 points

		if Card.Wasabi in hand and Card.SquidNigiri in hand and not get_num_unused_wasabi(plate):
			return Pick(Card.Wasabi, Card.SquidNigiri)  # 9 points

		if Card.Dumpling in hand_count and hand_count[Card.Dumpling] >= 2 and count_card(plate, Card.Dumpling) == 3:
			return Pick(Card.Dumpling, Card.Dumpling)  # 9 points
		
		# TOOD: wasabi-salmon? 2 tempura? 2 sashimi when num_sashimi_needed == 3?

	# Pick first card

	card1, _ = _random_plus_pick_card(
		plate=plate, hand=hand, verbose=verbose, take_obvious_picks=take_obvious_picks)

	# TODO: this blocks rare case of using chopsticks to take 2 chopsticks
	if (card1 == Card.Chopsticks):
		return Pick(card1)

	if can_use_chopsticks:

		# Pick possible 2nd card

		plate_after = list(plate)
		hand_after = list(hand)
		plate_after.append(card1)
		hand_after.remove(card1)

		card2, card2_state = _random_plus_pick_card(
			plate=plate_after, hand=hand_after, verbose=verbose, take_obvious_picks=take_obvious_picks)

		if card2 == Card.Chopsticks:
			return Pick(card1)

		elif card2_state == _RandomPickState.great:
			return Pick(card1, card2)
		
		elif card2_state == _RandomPickState.fine and (should_use_chopsticks or random_bool()):
			return Pick(card1, card2)

		elif card2_state == _RandomPickState.useless_to_me and should_use_chopsticks:
			return Pick(card1, card2)

	return Pick(card1)





"""
A very simple AI that's mostly random, but makes a few obvious choices (when possible):
	- Don't pick a card that's guaranteed to be useless:
		- More than 5 dumplings
		- Sets that will be impossible to complete (based only on number of cards left - doesn't keep track of other hands)
		- Chopsticks on 2nd last turn
		- More wasabi than turns left
	- Don't pick card that's straight worse than another
		- e.g. if 3-maki is available, don't take 1- or 2-maki
	- Always use chopsticks on 2nd last turn (if there's a point)
"""
class RandomPlusAI(PlayerInterface):
	@staticmethod
	def get_name() -> str:
		return "RandomPlusAI"

	@staticmethod
	def play_turn(player_state: PlayerState, verbose=False) -> Pick:
		return _random_plus_pick_cards(player_state=player_state, take_obvious_picks=False, verbose=verbose)


"""
A very simple AI that's mostly random, but makes a few obvious choices (when possible):
	- Don't pick a card that's guaranteed to be useless:
		- More than 5 dumplings
		- Sets that will be impossible to complete (based only on number of cards left - doesn't keep track of other hands)
		- Chopsticks on 2nd last turn
		- More wasabi than turns left
	- Don't pick card that's straight worse than another
		- e.g. if 3-maki is available, don't take 1- or 2-maki
	- Always use chopsticks on 2nd last turn (if there's a point)
	- If take_obvious_picks=True, then always take a few hard-coded picks if they come up:
		- Complete a set if possible
		- If we have an unused wasabi, take a squid
"""
class RandomPlusPlusAI(PlayerInterface):
	@staticmethod
	def get_name() -> str:
		return "RandomPlusPlusAI"

	@staticmethod
	def play_turn(player_state: PlayerState, verbose=False) -> Pick:
		return _random_plus_pick_cards(player_state=player_state, take_obvious_picks=True, verbose=verbose)


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

