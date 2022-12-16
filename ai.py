from player import PlayerState
from cards import *
from utils import *
import random


def random_ai(player_state, hand, verbose=False):
	assert len(hand) > 0
	return random.choice(hand)


# A very simple AI that's mostly random
# But makes a few obvious choices:
#   Don't pick card that's straight-up worse than another (e.g. maki1 if maki3 is available)
#   Complete a set if possible
#   Take a squid if we have a wasabi out
def basic_ai(player_state, hand, verbose=False):
	n_cards = len(hand)
	assert n_cards > 0
	hand_maybes = set(hand)

	if Cards.Maki3 in hand_maybes:
		hand_maybes.discard(Cards.Maki2)
		hand_maybes.discard(Cards.Maki1)
	elif Cards.Maki2 in hand_maybes:
		hand_maybes.discard(Cards.Maki1)

	if Cards.SquidNigiri in hand_maybes:
		hand_maybes.discard(Cards.SalmonNigiri)
		hand_maybes.discard(Cards.EggNigiri)
	elif Cards.SalmonNigiri in hand_maybes:
		hand_maybes.discard(Cards.EggNigiri)

	if Cards.Sashimi in hand_maybes:
		n_sashimi_needed = 3 - (count_card(player_state.plate, Cards.Sashimi) % 3)
		if n_sashimi_needed == 1:
			# Definitely take sashimi
			return Cards.Sashimi
		elif n_sashimi_needed > n_cards:
			# If it's not physically possibly to score this, don't take it
			hand_maybes.discard(Cards.Sashimi)

	if player_state.get_num_unused_wasabi() > 0 and Cards.SquidNigiri in hand_maybes:
		return Cards.SquidNigiri

	if Cards.Tempura in hand_maybes:
		n_tempura_needed = 2 - (count_card(player_state.plate, Cards.Sashimi) % 2)
		if n_tempura_needed == 1:
			return Cards.Tempura
		elif n_tempura_needed > n_cards:
			# If it's not physically possibly to score this, don't take it
			hand_maybes.discard(Cards.Tempura)

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

