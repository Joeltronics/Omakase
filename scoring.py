# I don't even know if this code will work with Python 2 or not, but here's a future import
# just in case, because this would be quite broken with Python 2 division
from __future__ import division

from cards import Cards
import cards
from utils import *


def score_tempura(plate):
	num_tempura = count_card(plate, Cards.Tempura)
	return 5 * (num_tempura // 2)


def score_sashimi(plate):
	num_sashimi = count_card(plate, Cards.Sashimi)
	return 10 * (num_sashimi // 3)


def count_maki(plate):
	num_maki = count_card(plate, Cards.Maki1)
	num_maki += 2 * count_card(plate, Cards.Maki2)
	num_maki += 3 * count_card(plate, Cards.Maki3)
	return num_maki


def score_dumplings(plate):
	
	num_dumpling = count_card(plate, Cards.Dumpling)
	
	if num_dumpling > 5:
		num_dumpling = 5
	
	return [0, 1, 3, 6, 10, 15][num_dumpling]


def score_nigiri(plate):

	# Note: for this, you can *either* convert the Nigiri into WasabiNigiri (and
	# then remove the Wasabi card from the plate), or if you just leave them all
	# on the plate (but in order)
	
	num_wasabi = 0
	score = 0

	def score_with_wasabi(nigiriScore, num_wasabi):
		if (num_wasabi > 0):
			nigiriScore *= 3
			num_wasabi -= 1
		return nigiriScore, num_wasabi
	
	for card in plate:
		card_score = 0
		if card is Cards.Wasabi:
			num_wasabi += 1
		
		elif card is Cards.EggNigiri:
			card_score, num_wasabi = score_with_wasabi(1, num_wasabi)
		
		elif card is Cards.SalmonNigiri:
			card_score, num_wasabi = score_with_wasabi(2, num_wasabi)
		
		elif card is Cards.SquidNigiri:
			card_score, num_wasabi = score_with_wasabi(3, num_wasabi)

		elif card is Cards.WasabiEggNigiri:
			card_score = 1*3

		elif card is Cards.WasabiSalmonNigiri:
			card_score = 2*3

		elif card is Cards.WasabiSquidNigiri:
			card_score = 3*3

		score += card_score

	return score


def score_plate(plate):
	# This only scores cards that count in a plate by itself
	# e.g. doesn't count Maki or Pudding
	
	score = 0
	score += score_tempura(plate)
	score += score_sashimi(plate)
	score += score_nigiri(plate)
	score += score_dumplings(plate)
	return score


def score_round(players, print_it=True):

	max_maki_count, points_most_maki, second_maki_count, points_second_most_maki = count_maki_players(players)

	if print_it:
		print('Scoring:')

	for player in players:
		score = score_plate(player.plate)

		maki = count_maki(player.plate)

		if maki == max_maki_count:
			score += points_most_maki
		elif maki == second_maki_count:
			score += points_second_most_maki

		if print_it:
			print("\t%s: %s, score: %i" % (player.name, cards.card_names(player.plate, sort=True), score))

		player.end_round(score)

	print()


def count_maki_players(players):

	nums_maki = []
	for player in players:
		maki = count_maki(player.plate)
		nums_maki.append(maki)

	nums_maki = sorted(nums_maki)

	# Now figure out how many points each number of maki is worth

	max_maki_count = max(nums_maki)

	if max_maki_count == 0:
		# Nobody has any Maki - 0 points all around
		return 0, 0, 0, 0

	num_players_max_maki_count = len([n for n in nums_maki if n == max_maki_count])
	nums_maki.remove(max_maki_count)
	second_maki_count = max(nums_maki)
	num_players_second_maki_count = len([n for n in nums_maki if n == second_maki_count])

	points_most_maki = 6 // num_players_max_maki_count
	points_second_most_maki = 3 // num_players_second_maki_count

	if (num_players_max_maki_count > 1) or (second_maki_count == 0):
		points_second_most_maki = 0

	return max_maki_count, points_most_maki, second_maki_count, points_second_most_maki


def count_pudding_players(players):
	assert len(players) > 1

	nums_pudding = []
	for player in players:
		nums_pudding.append(player.num_pudding)

	nums_pudding = sorted(nums_pudding)

	# Now figure out how many points each number of pudding is worth

	max_pudding_count = max(nums_pudding)
	min_pudding_count = min(nums_pudding)

	if max_pudding_count == min_pudding_count:
		# If everyone tied (possibly at 0)
		neg_points_least_pudding = 0

		if max_pudding_count > 0 and (players) == 2:
			points_most_pudding = 3
		else:
			points_most_pudding = 0

	else:
		num_players_max_count = len([n for n in nums_pudding if n == max_pudding_count])
		num_players_min_count = len([n for n in nums_pudding if n == min_pudding_count])
		points_most_pudding = 6 / num_players_max_count

		if len(players) == 2:
			neg_points_least_pudding = 0
		else:
			neg_points_least_pudding = 6 / num_players_min_count

	return max_pudding_count, points_most_pudding, min_pudding_count, neg_points_least_pudding


def score_puddings(players, print_it=True):
	max_pudding_count, points_most_pudding, min_pudding_count, neg_points_least_pudding = count_pudding_players(players)

	if print_it:
		print('Scoring pudding:')

	for player in players:

		score = 0

		# Have to check both max and min (not if-elif), in case max == min

		if player.num_pudding == max_pudding_count:
			score += points_most_pudding

		if player.num_pudding == min_pudding_count:
			score -= neg_points_least_pudding

		player.total_score += score

		if print_it:
			print("\t%s: %i pudding (%i points), total score: %i" % (player.name, player.num_pudding, score, player.total_score))


def _test():
	import random

	def ensure_score(plate, expected_score):
		score = score_plate(plate)
		if score != expected_score:
			print("Test failed!")
			print("Plate:")
			for card in plate:
				print("\t" + card.name)
			print("Expected score %i, actual %i" % (expected_score, score))
		assert score == expected_score

	# Tempura
	for n, s in enumerate([0, 0, 5, 5, 10, 10, 15, 15]):
		plate = [Cards.Tempura] * n
		ensure_score(plate, s)

	# Sashimi
	for n, s in enumerate([0, 0, 0, 10, 10, 10, 20, 20, 20, 30]):
		plate = [Cards.Sashimi] * n
		ensure_score(plate, s)

	# Dumpling
	for n, s in enumerate([0, 1, 3, 6, 10, 15, 15, 15, 15]):
		plate = [Cards.Dumpling] * n
		ensure_score(plate, s)

	# Nigiri + Wasabi, inline
	# 2 + 3x3 + 1 = 2 + 9 + 1 = 12
	plate = [Cards.SalmonNigiri, Cards.Wasabi, Cards.SquidNigiri, Cards.EggNigiri]
	ensure_score(plate, 12)

	# Nigiri + Wasabi, using WasabiNigiri cards
	# 2 + 3x3 + 1 = 2 + 9 + 1 = 12
	plate = [Cards.SalmonNigiri, Cards.WasabiSquidNigiri, Cards.EggNigiri]
	ensure_score(plate, 12)

	#ensure_score(plate, 13) # DEBUG

	# 5 tempura = 10 points
	# 4 sashimi = 10 points
	# 6 dumplings = 15 points
	# Egg = 1 point
	# Salmon = 2 points
	# Squid = 3 points
	# Total:  41
	plate = []
	plate += [Cards.Tempura] * 5
	plate += [Cards.Sashimi] * 4
	plate += [Cards.Dumpling] * 6
	plate += [Cards.EggNigiri, Cards.SalmonNigiri, Cards.SquidNigiri]
	random.shuffle(plate)
	ensure_score(plate, 41)

_test()
