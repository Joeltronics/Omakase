#!/usr/bin/env python

from collections import deque
from collections.abc import Collection, Sequence
from copy import copy, deepcopy
from dataclasses import dataclass, field
from functools import total_ordering
import itertools
from math import copysign, factorial, sqrt
from numbers import Real
from typing import List, Literal, Optional, Tuple, Union

from cards import Card, Pick, card_names
from player import CommonGameState, PlayerInterface, PlayerState
from probablistic_scoring import ProbablisticScorer
import scoring
from utils import count_card, get_all_picks


# Pudding count is tiebreaker, so your actual "score" for rank purposes is a tuple of (points, puddings)
# But the number of puddings is meaningless without the context of number of points, so it doesn't make
# sense to keep track of "average puddings"
# So instead, consolidate points & puddings into a single number, where puddings are scaled low enough
# that they shouldn't significantly affect the numbers from points
PUDDING_TIEBREAKER_SCALE = (1.0 / 1024.0)


# In practice, we care more about point differential to players close to us than far away
# e.g. if we're in a close battle for 1st, then 1 point difference from that player is much more important than
# 1 point difference to someone 20 points behind
# So use square root of score difference instead
SQRT_SCORE_DIFFERENTIAL = True


@total_ordering
@dataclass(frozen=True, order=True)
class Result:

	# Negative for the sake of ordering
	# -1 = 1st place, -2 = 2nd place, etc
	neg_rank: Real

	# Sum of differential of points to other players (adjusted for number of puddings as tiebreaker)
	# May be calculated with square root of difference, see SQRT_SCORE_DIFFERENTIAL
	score_differential: Real

	# Points, adjusted for number of puddings as tiebreaker
	score_total: Real

	# Disabled for performance purposes
	# def __post_init__(self):
	# 	if self.neg_rank >= 0:
	# 		raise ValueError(f'neg_rank must be negative! ({self.neg_rank})')

	def __add__(self, other) -> 'Result':
		return Result(
			neg_rank = self.neg_rank + other.neg_rank,
			score_differential = self.score_differential + other.score_differential,
			score_total = self.score_total + other.score_total,
		)

	def __truediv__(self, divisor: Real) -> 'Result':
		return Result(
			neg_rank = self.neg_rank / divisor,
			score_differential = self.score_differential / divisor,
			score_total = self.score_total / divisor,
		)


"""
'worst' = safest worst-case. Essentially assume we will always get blocked.
'best' = always rely on assuming we will hit best-case scenario. Probably not realistic.
'average' = target best average (assuming others play randomly)

TODO: true minimax (calculate optimal move for other players)
"""
ConsolidationType = Literal['best', 'worst', 'average']


# TODO: slots=True (Python >= 3.10)
@dataclass
class ConsolidatedResults:
	best: Result
	average: Result
	worst: Result

	def is_better_than(
			self,
			other: 'ConsolidatedResults',
			last_round: bool,
			consolidation_type: ConsolidationType = 'average',
			) -> bool:

		if consolidation_type == 'best':
			if last_round:
				return (self.best, self.average.neg_rank) > (other.best, other.average.neg_rank)
			else:
				return (self.best, self.average.score_differential) > (other.best, other.average.score_differential)

		elif consolidation_type == 'worst':
			if last_round:
				return (self.worst, self.average.neg_rank) > (other.worst, other.average.neg_rank)
			else:
				return (self.worst, self.average.score_differential) > (other.worst, other.average.score_differential)

		elif consolidation_type == 'average':
			if last_round:
				return \
					(self.average.neg_rank,  self.average.score_differential,  self.average.score_total) > \
					(other.average.neg_rank, other.average.score_differential, other.average.score_total)
			else:
				return \
					(self.average.score_differential,  self.average.neg_rank,  self.average.score_total) > \
					(other.average.score_differential, other.average.neg_rank, other.average.score_total)

		else:
			raise KeyError(f'Invalid ConsolidationType: "{consolidation_type}"')


"""
PlayerState is pretty heavyweight, this is a lighter subset of info for use with large recursive trees
"""
# TODO: slots=True (Python >= 3.10)
@dataclass
class _MinimalPlayerState:
	total_scores: list[int]
	num_puddings: list[int]
	plates: list[list[Card]]
	hands: deque[deque[Card]]

	def __post_init__(self):
		if not (len(self.total_scores) == len(self.num_puddings) == len(self.plates) == len(self.hands)):
			raise ValueError('All must have same length!')

	@property
	def num_players(self):
		return len(self.total_scores)

	@classmethod
	def from_player_state(cls, player_state: PlayerState):

		if player_state.any_unknown_cards:
			raise ValueError('Cannot use recursive solving when there are unknown cards!')

		hands = deque([deque(s.hand) for s in player_state.other_player_states])
		assert not any(Card.Unknown in h for h in hands)
		hands.appendleft(player_state.hand)

		total_scores = [player_state.public_state.total_score] + [s.total_score for s in player_state.other_player_states]
		num_puddings = [player_state.public_state.num_pudding] + [s.num_pudding for s in player_state.other_player_states]
		plates = [copy(player_state.public_state.plate)] + [copy(s.plate) for s in player_state.other_player_states]

		return cls(
			total_scores=total_scores,
			num_puddings=num_puddings,
			plates=plates,
			hands=hands,
		)

	def copy_with_played_cards(self, *picks) -> '_MinimalPlayerState':

		if len(picks) != len(self.hands):
			raise ValueError(f'Invalid length: {len(picks)} != {len(self.hands)}')

		ret = deepcopy(self)

		for pick, plate, hand in zip(picks, ret.plates, ret.hands):
			for card in pick:
				hand.remove(card)  # raises ValueError if card not in hand
				plate.append(card)
			if len(pick) == 2:
				hand.append(Card.Chopsticks)

		ret.hands.rotate(1)

		return ret

	def play_last_cards_and_score(
			self,
			probablistic_scorer: ProbablisticScorer,
			sqrt_score_differential=SQRT_SCORE_DIFFERENTIAL,
			) -> Result:
		"""
		:note: Invalidates this object
		"""

		assert all(len(h) == 1 for h in self.hands)
		for plate, hand in zip(self.plates, self.hands):
			plate.append(hand[0])

		plate = self.plates[0]

		round_scores = scoring.score_plates(self.plates)

		for idx in range(self.num_players):
			self.total_scores[idx] += round_scores[idx]
			self.num_puddings[idx] += count_card(self.plates[idx], Card.Pudding)

		# TODO: will need to pass in opportunity cost of playing a pudding instead of another card once ProbablisticScorer implements it
		# (Normally the recursive solver doesn't need to worry about opportunity costs, but this is different because it's for future rounds)
		pudding_scores = probablistic_scorer.score_puddings(self.num_puddings)
		for idx in range(self.num_players):
			self.total_scores[idx] += pudding_scores[idx]

		# Rank is less meaningful before final round, but not totally useless
		ranks = scoring.rank_players([
			scoring.ScoreAndPudding(total_score=score, num_pudding=pudding)
			for score, pudding in zip(self.total_scores, self.num_puddings)
		])
		my_neg_rank = -ranks[0]

		for idx in range(self.num_players):
			self.total_scores[idx] += PUDDING_TIEBREAKER_SCALE * self.num_puddings[idx]

		my_score = self.total_scores[0]

		if sqrt_score_differential:
			score_differential = sum(
				copysign(sqrt(abs(my_score - score)), my_score - score)
				for score in self.total_scores[1:]
			)
		else:
			score_differential = sum(
				my_score - score
				for score in self.total_scores[1:]
			)

		return Result(
			neg_rank=my_neg_rank,
			score_differential=score_differential,
			score_total=my_score,
		)


def _solve_recursive(
		player_state: _MinimalPlayerState,
		last_round: bool,
		probablistic_scorer: ProbablisticScorer,
		consolidation_type: ConsolidationType = 'average',
		recursion_depth=0,
		prune_my_bad_picks=True,
		prune_others_bad_picks=True,
		verbose=False,
		) -> Tuple[Pick, Optional[Result]]:

	assert recursion_depth < 10, "This recursion depth should not be possible - something went wrong!"

	need_result = (recursion_depth != 0)

	hand = player_state.hands[0]
	plate = player_state.plates[0]

	if not hand:
		raise ValueError('Empty hand!')

	num_cards = len(hand)

	if num_cards == 1:
		pick = Pick(hand[0])
		result = player_state.play_last_cards_and_score(probablistic_scorer=probablistic_scorer)
		return pick, result

	my_pick_options = get_all_picks(hand, plate=plate, prune_likely_bad_picks=prune_my_bad_picks)

	other_players_options = [
		get_all_picks(other_player_hand, plate=other_player_plate, prune_likely_bad_picks=prune_others_bad_picks)
		for other_player_hand, other_player_plate
		in zip(itertools.islice(player_state.hands, 1, None), player_state.plates[1:])
	]

	# TODO: Prune to a few best picks (both ours and others') based on some metrics
	# TODO: Also use these same metrics to determine likelihood other players will actually choose them,
	# and use this as basis for weighted average for Result
	# TODO: Also, proper minimax - i.e. calculate optimal play for all other players and use that

	# TODO: Try reconstructing this every time instead of copying it into a list, see if it affects performance
	other_players_options_product = list(itertools.product(*other_players_options))

	indent = '    ' * (1 + recursion_depth) if verbose else ''

	if verbose:
		print(
			f'{indent}My hand: {card_names(hand)}; '
			f'my options: {card_names(my_pick_options)}; '
			'other player options: [' + ', '.join(card_names(p, short=True) for p in other_players_options) + ']'
		)

	if len(my_pick_options) == 1 and not need_result:
		only_option = list(my_pick_options)[0]
		if verbose:
			print(f'{indent}Only option is {only_option}')
		return only_option, None

	best_pick_result = None
	for pick_option in my_pick_options:
		pick_result = None

		if verbose:
			if len(my_pick_options) == 1:
				print(f'{indent}Only option is {pick_option}, calculating result:')
			else:
				print(f'{indent}If I play {pick_option}:')

		num_other_player_possibilities = 0
		for other_player_option in other_players_options_product:
			num_other_player_possibilities += 1

			next_player_state = player_state.copy_with_played_cards(pick_option, *other_player_option)

			is_last_recursion_level = len(next_player_state.hands[0]) == 1

			if verbose and not is_last_recursion_level:
				print(f'{indent}  If others play {card_names(other_player_option, short=True)}:')

			_, next_pick_result = _solve_recursive(
				player_state=next_player_state,
				last_round=last_round,
				probablistic_scorer=probablistic_scorer,
				consolidation_type=consolidation_type,
				recursion_depth=recursion_depth + 1,
				prune_my_bad_picks=prune_my_bad_picks,
				prune_others_bad_picks=prune_others_bad_picks,
				verbose=verbose,
			)

			if verbose:
				if is_last_recursion_level:
					print(f'{indent}  If others play {card_names(other_player_option, short=True)}: {next_pick_result}')
				else:
					print(f'{indent}    {next_pick_result}')

			if pick_result is None:
				pick_result = ConsolidatedResults(best=next_pick_result, worst=next_pick_result, average=next_pick_result)
			else:
				pick_result.best = max(pick_result.best, next_pick_result)
				pick_result.worst = min(pick_result.worst, next_pick_result)
				pick_result.average += next_pick_result

			# TODO: break loop if we can already tell this is clearly a worse pick than our current best_pick_result

		assert num_other_player_possibilities > 0
		assert pick_result is not None
		assert isinstance(pick_result, ConsolidatedResults)

		pick_result.average /= num_other_player_possibilities

		if verbose:
			print(f'{indent}  Results if I play {pick_option}:')
			print(f'{indent}    Best:  rank {-pick_result.best.neg_rank:.2f}, point diff {pick_result.best.score_differential:+.2g}')
			print(f'{indent}    Avg:   rank {-pick_result.average.neg_rank:.2f}, point diff {pick_result.average.score_differential:+.2g}')
			print(f'{indent}    Worst: rank {-pick_result.worst.neg_rank:.2f}, point diff {pick_result.worst.score_differential:+.2g}')

		if (best_pick_result is None) or pick_result.is_better_than(best_pick_result[1], last_round=last_round, consolidation_type=consolidation_type):
			best_pick_result = (pick_option, pick_result)

		# TODO: if this is the last round and worst-case rank is 1, can exit the loop early because we know we've won

	assert best_pick_result is not None
	assert isinstance(best_pick_result[0], Pick)
	assert isinstance(best_pick_result[1], ConsolidatedResults)

	best_pick, best_pick_result = best_pick_result

	if consolidation_type == 'best':
		result = best_pick_result.best
	elif consolidation_type == 'worst':
		result = best_pick_result.worst
	elif consolidation_type == 'average':
		result = best_pick_result.average
	else:
		raise KeyError(f'Invalid ConsolidationType: "{consolidation_type}"')

	if verbose:
		print(f'{indent}Best result: {best_pick} (rank {-result.neg_rank:.2f}, point diff {result.score_differential:+.2g})')

	return best_pick, result


def solve_recursive(
		player_state: PlayerState,
		consolidation_type: ConsolidationType = 'average',
		verbose=False,
		) -> Pick:

	hand = player_state.hand

	if not hand:
		raise ValueError('Empty hand!')

	num_cards = len(hand)
	if num_cards == 1:
		return Pick(hand[0])

	if (Card.Chopsticks not in player_state.plate) and len(set(hand)) == 1:
		return Pick(hand[0])

	num_players = 1 + len(player_state.other_player_states)

	minimal_player_state = _MinimalPlayerState.from_player_state(player_state)

	# Base number of possibilities: how big the "tree size" is
	# But this is assuming no chopsticks, and that all cards are unique (and viable picks)
	#
	# 2 players = 10 cards, first know all hands on turn 2 (9 cards in hand)
	# Turn 2, 9 cards:        1e11
	# Turn 3, 8 cards:        2e9
	# Turn 4, 7 cards:        3e7
	# Turn 5, 6 cards:  518,499
	# Turn 6, 5 cards:   14,400
	# Turn 7, 4 cards:      576
	# Turn 8, 3 cards:       36
	# Turn 9, 2 cards:        4
	#
	# 3 players = 9 cards, first know all hands on turn 3 (7 cards in hand)
	# Turn 3, 7 cards:         1e11
	# Turn 4, 6 cards:         4e8
	# Turn 5, 5 cards: 1,728,000
	# Turn 6, 4 cards:    13,284
	# Turn 7, 3 cards:       215
	# Turn 8, 2 cards:         9
	#
	# 4 players = 8 cards, first know all hands on turn 4 (5 cards in hand)
	# Turn 4, 5 cards:         2e8
	# Turn 5, 4 cards:   331,776
	# Turn 6, 3 cards:     1,296
	# Turn 7, 2 cards:        16
	#
	# 5 players = 7 cards, first know all hands on turn 5 (3 cards in hand)
	# Turn 5, 3 cards:     7,776
	# Turn 6, 2 cards:        32
	# TODO: also attempt to factor in chopsticks
	base_num_possibilities = factorial(num_cards) ** num_players

	if verbose:
		print(f'Brute force solving - base tree size: {base_num_possibilities} (assuming no chopsticks, and all cards are unique and good choices)')
		# TODO: also have _solve_recursive() return total number of combinations tried so we can compare

	# In 3+ player game, pareto optimality isn't always clear as it seems
	# In other words, there are rare cases where a "bad pick" can actually be better for us
	#
	# e.g. Hand is [Maki3, Maki1], but we can't possibly get points from Maki, and someone who can is also competing
	# for the same cards we are - taking Maki1 causes them to take the Maki3, which leaves the card we want
	#
	# This is quite rare, so in most cases it's not worth the performance cost of considering these picks
	# (Everything here is multiplicative, so even excluding just 1 option can make a good dent in the overall tree size)
	prune_my_bad_picks = (num_players < 3) or (base_num_possibilities > 2000)
	prune_others_bad_picks = (num_players < 3) or (base_num_possibilities > 200)

	probablistic_scorer = ProbablisticScorer(player_state)

	pick, _ = _solve_recursive(
		player_state=minimal_player_state,
		last_round=player_state.common_game_state.last_round,
		probablistic_scorer=probablistic_scorer,
		consolidation_type=consolidation_type,
		prune_my_bad_picks=prune_my_bad_picks,
		prune_others_bad_picks=prune_others_bad_picks,
		verbose=verbose,
	)
	assert isinstance(pick, Pick)
	return pick


class RecursiveSolverAI(PlayerInterface):
	@staticmethod
	def get_name() -> str:
		return "RecursiveSolverAI"

	@staticmethod
	def play_turn(player_state: PlayerState, hand: Collection[Card], verbose=False) -> Pick:
		assert hand == player_state.hand
		return solve_recursive(player_state=player_state, verbose=verbose)