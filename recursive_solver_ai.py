#!/usr/bin/env python

from collections import deque
from collections.abc import Collection, Sequence
from copy import copy, deepcopy
from dataclasses import dataclass, field
from enum import IntEnum, unique
import itertools
from math import copysign, factorial, sqrt
from numbers import Real
from typing import List, Literal, Optional, Tuple, Union

from cards import Card, Pick, Plate, card_names
from player import PlayerInterface, PlayerState
from probablistic_scoring import ProbablisticScorer
import scoring
from utils import container_to_str, count_card, get_all_picks


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


@unique
class Verbosity(IntEnum):
	silent = 0
	verbose = 1
	extra_verbose = 2
	extra_verbose_recursive = 3


VERBOSITY = Verbosity.verbose
# VERBOSITY = Verbosity.extra_verbose
# VERBOSITY = Verbosity.extra_verbose_recursive


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

	def __str__(self) -> str:
		return f'Result(rank={-self.neg_rank:.2g}, score_differential={self.score_differential:+.3f}, score_total={self.score_total:.3f})'

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
	plates: list[Plate]
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

		hands = deque(deque(hand) for hand in player_state.hands)
		total_scores = [s.total_score for s in player_state.public_states]
		num_puddings = [s.num_pudding for s in player_state.public_states]
		plates = [copy(s.plate) for s in player_state.public_states]

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

		for idx, (pick, plate, hand) in enumerate(zip(picks, ret.plates, ret.hands)):
			for card in pick:
				hand.remove(card)  # raises ValueError if card not in hand
				plate.add(card)
				if card == Card.Pudding:
					ret.num_puddings[idx] += 1
			if len(pick) == 2:
				hand.append(Card.Chopsticks)

		ret.hands.rotate(1)

		return ret

	def play_last_cards_and_score(
			self,
			probablistic_scorer: ProbablisticScorer,
			sqrt_score_differential=SQRT_SCORE_DIFFERENTIAL,
			verbose: bool = False,
			indent: str = '',
			) -> Result:
		"""
		:note: Invalidates this object
		"""

		assert self.hands[0] is not self.hands[-1]

		for idx, (plate, hand) in enumerate(zip(self.plates, self.hands)):
			assert len(hand) == 1
			plate.add(hand[0])
			if hand[0] == Card.Pudding:
				self.num_puddings[idx] += 1

		plate = self.plates[0]

		round_scores = scoring.score_plates(self.plates)

		for idx in range(self.num_players):
			self.total_scores[idx] += round_scores[idx]

		# TODO: will need to pass in opportunity cost of playing a pudding instead of another card once ProbablisticScorer implements it
		# (Normally the recursive solver doesn't need to worry about opportunity costs, but this is different because it's for future rounds)
		pudding_scores = probablistic_scorer.end_of_round_score_puddings(self.num_puddings)
		for idx in range(self.num_players):
			self.total_scores[idx] += pudding_scores[idx]

		# Rank is less meaningful before final round, but not totally useless
		ranks = scoring.rank_players([
			scoring.ScoreAndPudding(total_score=score, num_pudding=pudding)
			for score, pudding in zip(self.total_scores, self.num_puddings)
		])
		my_neg_rank = -ranks[0]

		if verbose:
			print(f'{indent}Scores: {round_scores} + pudding: ({self.num_puddings} -> {container_to_str(pudding_scores, "{:.2g}")}) = rank {ranks}')

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
		verbose=Verbosity.silent,
		) -> Tuple[Pick, Optional[Result]]:

	assert recursion_depth < 10, "This recursion depth should not be possible - something went wrong!"

	indent = '    ' * (1 + recursion_depth) if verbose else ''

	extra_verbose = verbose >= Verbosity.extra_verbose
	extra_verbose_recursive = verbose >= Verbosity.extra_verbose_recursive

	need_result = (recursion_depth != 0)

	hand = player_state.hands[0]
	plate = player_state.plates[0]

	if not hand:
		raise ValueError('Empty hand!')

	num_cards = len(hand)

	if num_cards == 1:
		pick = Pick(hand[0])
		result = player_state.play_last_cards_and_score(probablistic_scorer=probablistic_scorer, verbose=extra_verbose_recursive, indent=indent)
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

		if extra_verbose:
			if len(my_pick_options) == 1:
				print(f'{indent}Only option is {pick_option}, calculating result:')
			else:
				print(f'{indent}If I play {pick_option}:')

		num_other_player_possibilities = 0
		for other_player_option in other_players_options_product:
			num_other_player_possibilities += 1

			next_player_state = player_state.copy_with_played_cards(pick_option, *other_player_option)

			is_last_recursion_level = len(next_player_state.hands[0]) == 1

			# if extra_verbose and not is_last_recursion_level:
			if extra_verbose:
				print(f'{indent}  If others play {card_names(other_player_option, short=True)}:')

			_, next_pick_result = _solve_recursive(
				player_state=next_player_state,
				last_round=last_round,
				probablistic_scorer=probablistic_scorer,
				consolidation_type=consolidation_type,
				recursion_depth=recursion_depth + 1,
				prune_my_bad_picks=prune_my_bad_picks,
				prune_others_bad_picks=prune_others_bad_picks,
				verbose = (verbose if extra_verbose_recursive else Verbosity.silent),
			)

			if extra_verbose:
				if is_last_recursion_level:
					# TODO: maybe break down scoring?
					# print(f'{indent}  If others play {card_names(other_player_option, short=True)}: {next_pick_result}')
					print(f'{indent}    {next_pick_result}')
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

		if extra_verbose:
			print(f'{indent}  Results if I play {pick_option}:')
			print(f'{indent}    Best:  rank {-pick_result.best.neg_rank:.2f}, point diff {pick_result.best.score_differential:+.2g}')
			print(f'{indent}    Avg:   rank {-pick_result.average.neg_rank:.2f}, point diff {pick_result.average.score_differential:+.2g}')
			print(f'{indent}    Worst: rank {-pick_result.worst.neg_rank:.2f}, point diff {pick_result.worst.score_differential:+.2g}')
		elif verbose:
			print(f'{indent}{str(pick_option) + ":":20s} Rank {-pick_result.best.neg_rank:.2g} / {-pick_result.average.neg_rank:.2f} / {-pick_result.worst.neg_rank:.2g}; Point diff {pick_result.best.score_differential:+.2g} / {pick_result.average.score_differential:+.2g} / {pick_result.worst.score_differential:+.2g}')

		# TODO: explicitly handle ties (right now it's just based on the order they get iterated in a set)
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

	if extra_verbose:
		print(f'{indent}Best result: {best_pick} (rank {-result.neg_rank:.2f}, point diff {result.score_differential:+.2g})')

	return best_pick, result


def solve_recursive(
		player_state: PlayerState,
		consolidation_type: ConsolidationType = 'average',
		verbose=False,
		) -> Pick:

	verbosity = (VERBOSITY if verbose else Verbosity.silent)

	hand = player_state.hand

	if not hand:
		raise ValueError('Empty hand!')

	num_cards = len(hand)
	if num_cards == 1:
		return Pick(hand[0])

	if (not player_state.plate.chopsticks) and len(set(hand)) == 1:
		return Pick(hand[0])

	num_players = 1 + len(player_state.other_player_states)

	minimal_player_state = _MinimalPlayerState.from_player_state(player_state)

	"""
	Base number of possibilities: how big the "tree size" is
	But this is assuming no chopsticks, and that all cards are unique (and viable picks)
	
	2 players = 10 cards, first know all hands on turn 2 (9 cards in hand)
	Turn 2, 9 cards:        1e11
	Turn 3, 8 cards:        2e9
	Turn 4, 7 cards:        3e7
	Turn 5, 6 cards:  518,499
	Turn 6, 5 cards:   14,400
	Turn 7, 4 cards:      576
	Turn 8, 3 cards:       36
	Turn 9, 2 cards:        4
	
	3 players = 9 cards, first know all hands on turn 3 (7 cards in hand)
	Turn 3, 7 cards:         1e11
	Turn 4, 6 cards:         4e8
	Turn 5, 5 cards: 1,728,000
	Turn 6, 4 cards:    13,284
	Turn 7, 3 cards:       215
	Turn 8, 2 cards:         9
	
	4 players = 8 cards, first know all hands on turn 4 (5 cards in hand)
	Turn 4, 5 cards:         2e8
	Turn 5, 4 cards:   331,776
	Turn 6, 3 cards:     1,296
	Turn 7, 2 cards:        16
	
	5 players = 7 cards, first know all hands on turn 5 (3 cards in hand)
	Turn 5, 3 cards:     7,776
	Turn 6, 2 cards:        32

	TODO: also attempt to factor in chopsticksexit()

	If we limit the max number of picks to 3 per step, then:

	4 players
	Turn 4, 5 cards: (3*3*3*2*1) ^ 4 = 8,503,056
	Turn 5, 4 cards: (3*3*2*1) ^ 4 =     104,976

	"""
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

	# TODO: when we have proper minimax, enable this for very low base_num_possibilities
	prune_others_bad_picks = True

	probablistic_scorer = ProbablisticScorer(player_state)

	pick, _ = _solve_recursive(
		player_state=minimal_player_state,
		last_round=player_state.common_game_state.last_round,
		probablistic_scorer=probablistic_scorer,
		consolidation_type=consolidation_type,
		prune_my_bad_picks=prune_my_bad_picks,
		prune_others_bad_picks=prune_others_bad_picks,
		verbose=verbosity,
	)
	assert isinstance(pick, Pick)
	return pick


class RecursiveSolverAI(PlayerInterface):
	def __init__(self, consolidation_type: ConsolidationType = 'average'):
		self.consolidation_type = consolidation_type

	def get_name(self) -> str:
		if self.consolidation_type == 'average':
			return "RecursiveSolverAI(Average)"
		elif self.consolidation_type == 'worst':
			return "RecursiveSolverAI(Pessimistic)"
		elif self.consolidation_type == 'best':
			return "RecursiveSolverAI(Optimistic)"
		else:
			assert False, f"Invalid ConsolidationType: {self.consolidation_type}"

	def play_turn(self, player_state: PlayerState, verbose=False) -> Pick:
		return solve_recursive(player_state=player_state, consolidation_type=self.consolidation_type, verbose=verbose)


class LaterRecursiveAI(PlayerInterface):
	def __init__(self, non_recursive_ai: PlayerInterface, max_recursive_hand_size: int = 3, consolidation_type: ConsolidationType = 'average'):
		self.non_recursive_ai = non_recursive_ai
		# TODO: optionally a variable recursive hand size per number of players (i.e. might want higher when fewer players)
		self.max_recursive_hand_size = max_recursive_hand_size
		# TODO: optionally a different consolidation type for 2-player games
		self.consolidation_type = consolidation_type

	def get_name(self) -> str:
		if self.consolidation_type == 'average':
			return "LaterRecursiveAI(Average)"
		elif self.consolidation_type == 'worst':
			return "LaterRecursiveAI(Pessimistic)"
		elif self.consolidation_type == 'best':
			return "LaterRecursiveAI(Optimistic)"
		else:
			assert False, f"Invalid ConsolidationType: {self.consolidation_type}"

	def play_turn(self, player_state: PlayerState, verbose=False) -> Pick:
		if len(player_state.hand) > self.max_recursive_hand_size or player_state.any_unknown_cards:
			return self.non_recursive_ai.play_turn(player_state=player_state, verbose=verbose)
		else:
			return solve_recursive(player_state=player_state, consolidation_type=self.consolidation_type, verbose=verbose)
