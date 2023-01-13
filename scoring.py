#!/usr/bin/env python

from collections import namedtuple
from collections.abc import Sequence
from typing import List, Union

from cards import Card, Plate
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


def score_plate_besides_maki_pudding(plate: Sequence[Card]) -> int:
	# This only scores cards that count in a plate by itself
	# e.g. doesn't count Maki or Pudding
	
	score = 0
	score += score_tempura(plate)
	score += score_sashimi(plate)
	score += score_nigiri(plate)
	score += score_dumplings(plate)
	return score


def _check_plate(player: PlayerState) -> None:
	"""
	Sanity check that player.plate matches what's in player.play_history
	"""

	# Reconstruct plate as sequence
	reconstructed_plate = []
	for pick in player.play_history:
		if len(pick) == 2:
			if Card.Chopsticks not in reconstructed_plate:
				raise ValueError(f'Invalid play history: {player.play_history}')
			reconstructed_plate.remove(Card.Chopsticks)
		for card in pick:
			reconstructed_plate.append(card)

	# Check the values that are needed for scoring
	expected_score = score_plate_besides_maki_pudding(reconstructed_plate)
	assert expected_score == player.plate.score, f'{reconstructed_plate=} {expected_score=} {player.plate.score=}'

	assert count_maki(reconstructed_plate) == player.plate.maki, f'{reconstructed_plate=} {count_maki(reconstructed_plate)=} {player.plate.maki=}'


def score_maki(nums_maki: Sequence[int]) -> List[int]:

	max_maki_count, points_most_maki, second_maki_count, points_second_most_maki = _count_maki_plates(nums_maki)

	def _score_maki(num_maki: int):
		if num_maki == max_maki_count:
			return points_most_maki
		elif num_maki == second_maki_count:
			return points_second_most_maki
		else:
			return 0

	return [_score_maki(num_maki) for num_maki in nums_maki]


def score_plates(plates_or_players: Union[Sequence[PlayerState], Sequence[Plate]], /) -> list[int]:

	if not plates_or_players:
		return []
	elif isinstance(plates_or_players[0], PlayerState):
		players = plates_or_players
		for player in players:
			_check_plate(player)
		plates = [player.plate for player in players]
	else:
		assert isinstance(plates_or_players[0], Plate)
		plates = plates_or_players

	maki_scores = score_maki([plate.maki for plate in plates])

	return [plate.score + maki_score for plate, maki_score in zip(plates, maki_scores)]


def score_round_players(players: Sequence[PlayerState], print_it=True):

	plate_scores = score_plates(players)

	# TODO: maybe print Maki counts, and separate breakdown of points from Maki?
	if print_it:
		print('Scoring:')

	for player, round_score in zip(players, plate_scores):
		if print_it:
			print("\t%s: %s, score: %i" % (player.name, cards.card_names(player.plate, sort=True), round_score))
		player.end_round(round_score)

	if print_it:
		print()


def _count_maki_plates(nums_maki: Sequence[int]) -> Tuple[int, int, int, int]:

	assert len(nums_maki) >= 2

	nums_maki = sorted(nums_maki, reverse=True)

	max_maki_count = nums_maki[0]
	second_maki_count = nums_maki[1]

	if max_maki_count == 0:
		# Nobody has Maki
		return 0, 0, 0, 0

	num_players_max_maki_count = sum(n == max_maki_count for n in nums_maki)
	assert num_players_max_maki_count > 0
	points_most_maki = 6 // num_players_max_maki_count

	assert (num_players_max_maki_count > 1) == (max_maki_count == second_maki_count)

	if (num_players_max_maki_count > 1) or (second_maki_count == 0):
		points_second_most_maki = 0
	else:
		num_players_second_maki_count = sum(n == second_maki_count for n in nums_maki)
		assert num_players_second_maki_count > 0
		points_second_most_maki = 3 // num_players_second_maki_count

	return max_maki_count, points_most_maki, second_maki_count, points_second_most_maki


def _count_pudding(nums_pudding: Sequence[int]) -> Tuple[int, int, int, int]:
	num_players = len(nums_pudding)
	assert num_players > 1

	nums_pudding = sorted(nums_pudding)

	# Now figure out how many points each number of pudding is worth

	max_pudding_count = max(nums_pudding)
	min_pudding_count = min(nums_pudding)

	if max_pudding_count == min_pudding_count:
		# If everyone tied (possibly at 0)
		neg_points_least_pudding = 0

		if max_pudding_count > 0 and num_players == 2:
			points_most_pudding = 3
		else:
			points_most_pudding = 0

	else:
		num_players_max_count = len([n for n in nums_pudding if n == max_pudding_count])
		num_players_min_count = len([n for n in nums_pudding if n == min_pudding_count])
		points_most_pudding = 6 / num_players_max_count

		if num_players == 2:
			neg_points_least_pudding = 0
		else:
			neg_points_least_pudding = 6 / num_players_min_count

	return max_pudding_count, points_most_pudding, min_pudding_count, neg_points_least_pudding


def score_puddings(num_puddings: Sequence[int]) -> List[int]:

	max_pudding_count, points_most_pudding, min_pudding_count, neg_points_least_pudding = _count_pudding(num_puddings)

	def _score_pudding(num_pudding: int) -> int:
		if num_pudding == max_pudding_count:
			return points_most_pudding
		elif num_pudding == min_pudding_count:
			return -neg_points_least_pudding
		else:
			return 0

	return [_score_pudding(num_pudding) for num_pudding in num_puddings]


def score_player_puddings(players: Sequence[PlayerState], print_it=True):

	if print_it:
		print('Scoring pudding:')

	pudding_scores = score_puddings([p.num_pudding for p in players])

	for player, pudding_score in zip(players, pudding_scores):

		player.score_puddings(pudding_score)

		if print_it:
			print("\t%s: %i pudding (%i points), total score: %i" % (player.name, player.num_pudding, pudding_score, player.total_score))

	if print_it:
		print()


ScoreAndPudding = namedtuple('ScoreAndPudding', ['total_score', 'num_pudding'])


def rank_players(players: Sequence[Union[PlayerState, ScoreAndPudding]], print_it=False) -> List[int]:

	assert len(players) > 0

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
			print(f'\t{rank}: {player.name}')  # FIXME: will throw if using ScoreAndPudding option

	return player_ranks_list


def _test():
	import random

	def ensure_score(plate, expected_score):
		score = score_plate_besides_maki_pudding(plate)
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
