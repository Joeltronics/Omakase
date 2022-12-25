#!/usr/bin/env python

from collections.abc import Sequence
from typing import List

from cards import Card
import cards
from player import PlayerState
from utils import *


def score_tempura(plate: Sequence[Card]) -> int:
	num_tempura = count_card(plate, Card.Tempura)
	return 5 * (num_tempura // 2)


def score_sashimi(plate: Sequence[Card]) -> int:
	num_sashimi = count_card(plate, Card.Sashimi)
	return 10 * (num_sashimi // 3)


def count_maki(plate: Sequence[Card]) -> int:
	num_maki = count_card(plate, Card.Maki1)
	num_maki += 2 * count_card(plate, Card.Maki2)
	num_maki += 3 * count_card(plate, Card.Maki3)
	return num_maki


def score_dumplings(plate: Sequence[Card]) -> int:
	
	num_dumpling = count_card(plate, Card.Dumpling)
	
	num_dumpling = min(num_dumpling, 5)
	
	return [0, 1, 3, 6, 10, 15][num_dumpling]


def score_nigiri(plate: Sequence[Card]) -> int:

	# Note: for this, you can *either* convert the Nigiri into WasabiNigiri (and
	# then remove the Wasabi card from the plate), or if you just leave them all
	# on the plate (but in order)
	
	num_wasabi = 0
	score = 0

	def score_with_wasabi(nigiri_score, num_wasabi):
		if (num_wasabi > 0):
			nigiri_score *= 3
			num_wasabi -= 1
		return nigiri_score, num_wasabi
	
	for card in plate:
		card_score = 0
		if card is Card.Wasabi:
			num_wasabi += 1
		
		elif card is Card.EggNigiri:
			card_score, num_wasabi = score_with_wasabi(1, num_wasabi)
		
		elif card is Card.SalmonNigiri:
			card_score, num_wasabi = score_with_wasabi(2, num_wasabi)
		
		elif card is Card.SquidNigiri:
			card_score, num_wasabi = score_with_wasabi(3, num_wasabi)

		score += card_score

	return score


def score_plate(plate: Sequence[Card]) -> int:
	# This only scores cards that count in a plate by itself
	# e.g. doesn't count Maki or Pudding
	
	score = 0
	score += score_tempura(plate)
	score += score_sashimi(plate)
	score += score_nigiri(plate)
	score += score_dumplings(plate)
	return score


def score_round(players: Sequence[PlayerState], print_it=True):

	max_maki_count, points_most_maki, second_maki_count, points_second_most_maki = count_maki_players(players)

	if print_it:
		print('Scoring:')

	for player in players:
		round_score = score_plate(player.plate)

		maki = count_maki(player.plate)

		if maki == max_maki_count:
			round_score += points_most_maki
		elif maki == second_maki_count:
			round_score += points_second_most_maki

		if print_it:
			print("\t%s: %s, score: %i" % (player.name, cards.card_names(player.plate, sort=True), round_score))

		player.end_round(round_score)

	if print_it:
		print()


def count_maki_players(players: Sequence[PlayerState]):

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


def count_pudding_players(players: Sequence[PlayerState]):
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


def score_puddings(players: Sequence[PlayerState], print_it=True):
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

		player.score_puddings(score)

		if print_it:
			print("\t%s: %i pudding (%i points), total score: %i" % (player.name, player.num_pudding, score, player.total_score))

	if print_it:
		print()


def rank_players(players: Sequence[PlayerState], print_it=True) -> List[int]:

	unscored_players = {idx: player for idx, player in enumerate(players)}
	player_ranks = dict()

	# curr_rank = 1

	for rank in range(len(players)):

		"""
		With no ties, here's what we'll see at the start of each loop iteration:

		rank=0: player_ranks={}
		rank=1: player_ranks={<idx>: 0}
		rank=2: player_ranks={<idx>: 0, <idx>: 1}
		rank=3: player_ranks={<idx>: 0, <idx>: 1, <idx>: 2}

		If there's a tie for 1st (rank 0), then:

		rank=0: player_ranks={}
		rank=1: player_ranks={<idx>: 0, <idx>: 0} - skip this iteration
		rank=2: player_ranks={<idx>: 0, <idx>: 0}
		rank=3: player_ranks={<idx>: 0, <idx>: 0, <idx>: 2}
		"""
		if len(player_ranks) > rank:
			continue

		assert unscored_players

		max_score = max([p.total_score for p in unscored_players.values()])
		players_at_max_score = {idx: p for idx, p in unscored_players.items() if p.total_score == max_score}
		assert players_at_max_score

		if len(players_at_max_score) == 1:
			player_idx = next(iter(players_at_max_score))
			unscored_players.pop(player_idx)
			player_ranks[player_idx] = rank
			continue

		# Tiebreaker is max number of puddings

		max_num_puddings_of_players_at_max_score = max([p.num_pudding for p in players_at_max_score.values()])
		players_at_max_score_and_max_puddings = {
			idx: p for idx, p in players_at_max_score.items()
			if p.num_pudding == max_num_puddings_of_players_at_max_score
		}

		assert players_at_max_score_and_max_puddings

		# No 2nd tiebreaker; all remaining tied players share this rank

		for player_idx in players_at_max_score_and_max_puddings.keys():
			unscored_players.pop(player_idx)
			player_ranks[player_idx] = rank

	assert not unscored_players, 'Failed to score all players'
	assert sorted(list(player_ranks.keys())) == list(range(len(players))), 'Failed to score all players'

	# Convert to list, and 1-index
	player_ranks_list = [player_ranks[idx] + 1 for idx in range(len(players))]
	assert min(player_ranks_list) == 1

	if print_it:
		print('Final results:')
		for player, rank in sorted(zip(players, player_ranks_list), key=lambda p_r: p_r[1]):
			print(f'\t{rank}: {player.name}')

	return player_ranks_list


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
		plate = [Card.Tempura] * n
		ensure_score(plate, s)

	# Sashimi
	for n, s in enumerate([0, 0, 0, 10, 10, 10, 20, 20, 20, 30]):
		plate = [Card.Sashimi] * n
		ensure_score(plate, s)

	# Dumpling
	for n, s in enumerate([0, 1, 3, 6, 10, 15, 15, 15, 15]):
		plate = [Card.Dumpling] * n
		ensure_score(plate, s)

	# Nigiri + Wasabi, inline
	# 2 + 3x3 + 1 = 2 + 9 + 1 = 12
	plate = [Card.SalmonNigiri, Card.Wasabi, Card.SquidNigiri, Card.EggNigiri]
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
	plate += [Card.Tempura] * 5
	plate += [Card.Sashimi] * 4
	plate += [Card.Dumpling] * 6
	plate += [Card.EggNigiri, Card.SalmonNigiri, Card.SquidNigiri]
	random.shuffle(plate)
	ensure_score(plate, 41)

_test()
