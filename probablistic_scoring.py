#!/usr/bin/env python

from collections.abc import Sequence
from fractions import Fraction
from math import comb, isclose, prod
from numbers import Real
from typing import List, Optional

from cards import Card
from player import PlayerState
import scoring
from utils import count_card, count_maki, container_to_str


def _possible_matching_hands(
		cards_in_deck: int,
		this_card_in_deck: int,
		cards_dealing: int,
		this_card_dealt: int,
		) -> int:

	non_this_card_dealt = cards_dealing - this_card_dealt
	other_cards_in_deck = cards_in_deck - this_card_in_deck

	if non_this_card_dealt < 0 or other_cards_in_deck < 0:
		return 0

	# e.g. 52 card deck, odds of 3 aces:
	# (4 C 3) * (48 C 1)
	possible_matching_hands = \
		comb(this_card_in_deck, this_card_dealt) * \
		comb(other_cards_in_deck, non_this_card_dealt)

	return possible_matching_hands


def _total_possible_hands(
		cards_in_deck: int,
		cards_dealing: int,
		) -> int:
	return comb(cards_in_deck, cards_dealing)


def num_cards_odds(
		cards_in_deck: int,
		this_card_in_deck: int,
		cards_dealing: int,
		this_card_dealt: int,
		) -> Fraction:
	"""
	If I have a deck with cards_in_deck cards, and this_card_in_deck are card "X",
	and I deal cards_dealing cards, what are the odds we will get exactly this_card_dealt "X" cards?
	"""
	return Fraction(
		numerator=_possible_matching_hands(
			cards_in_deck=cards_in_deck, cards_dealing=cards_dealing,
			this_card_in_deck=this_card_in_deck, this_card_dealt=this_card_dealt),
		denominator=_total_possible_hands(
			cards_in_deck=cards_in_deck, cards_dealing=cards_dealing)
	)


def num_cards_odds_at_least(
		cards_in_deck: int,
		this_card_in_deck: int,
		cards_dealing: int,
		this_card_at_least: int,
		) -> Fraction:
	"""
	If I have a deck with cards_in_deck cards, and this_card_in_deck are card "X",
	and I deal cards_dealing cards, what are the odds we will get at least this_card_at_least "X" cards?
	"""

	if (this_card_at_least == 0) or (this_card_in_deck == 0):
		return Fraction(1, 1)

	total_possible_hands = _total_possible_hands(cards_in_deck=cards_in_deck, cards_dealing=cards_dealing)

	if this_card_at_least == 1:
		# "At least 1" is a common scenario, have a special case for it
		# Equivalent to 1 = P(0)
		total_zero_hands = _possible_matching_hands(
			cards_in_deck=cards_in_deck, cards_dealing=cards_dealing,
			this_card_in_deck=this_card_in_deck, this_card_dealt=0)
		assert 0 < total_zero_hands < total_possible_hands
		return Fraction(numerator=(total_possible_hands - total_zero_hands), denominator=total_possible_hands)

	# TODO: might be faster to similarly calculate the inverse whenever (this_card_at_least < this_card_in_deck/2)
	# TODO: there's also probably a way to calculate this directly instead of dynamically summing?
	matching_hands = sum(
		_possible_matching_hands(
				cards_in_deck=cards_in_deck,
				this_card_in_deck=this_card_in_deck,
				cards_dealing=cards_dealing,
				this_card_dealt=n)
		for n in range(this_card_at_least, min(this_card_in_deck, cards_dealing) + 1)
	)
	assert 0 <= matching_hands < total_possible_hands
	return Fraction(numerator=matching_hands, denominator=total_possible_hands)


def num_cards_odds_list(
		cards_in_deck: int,
		this_card_in_deck: int,
		cards_dealing: int,
		) -> List[Fraction]:
	"""
	If I have a deck with cards_in_deck cards, and this_card_in_deck are card "X",
	and I deal cards_dealing cards, what are the odds we will get exactly N "X" cards?
	"""
	if cards_dealing > cards_in_deck:
		raise ValueError(f'{cards_dealing=} > {cards_in_deck=}')
	if this_card_in_deck == 0 or cards_dealing == 0:
		return [Fraction(1, 1)]
	total_possible_hands = _total_possible_hands(cards_in_deck=cards_in_deck, cards_dealing=cards_dealing)
	assert total_possible_hands != 0, f"{cards_in_deck=}, {this_card_in_deck=}, {cards_dealing=}"
	return [
		Fraction(
			numerator=_possible_matching_hands(
				cards_in_deck=cards_in_deck,
				this_card_in_deck=this_card_in_deck,
				cards_dealing=cards_dealing,
				this_card_dealt=n),
			denominator=total_possible_hands
		)
		for n in range(min(this_card_in_deck, cards_dealing) + 1)
	]


def num_cards_odds_average(
		cards_in_deck: int,
		this_card_in_deck: int,
		cards_dealing: int,
		) -> Fraction:
	return sum(
		num_card * probability
		for num_card, probability in enumerate(
			num_cards_odds_list(
				cards_in_deck=cards_in_deck, this_card_in_deck=this_card_in_deck, cards_dealing=cards_dealing,
			)
		)
	)


def _delta_range_probabilities(
		counts: Sequence[int],
		player_idx: int,
		average_num_yet_to_see: float,
		include_self_as_none=False,
		verbose=False,
		) -> list[float]:
	"""
	For scoring Pudding or Maki, calculate probability that we beat each other player,
	based on what we'll call the "delta range approximation"

	This is a very simplified approximation, but it does an okay job

	=== Details ===

	Compare our number to each other player.

	Then, on a scale from "I take all remaining" to "they take all remaining",
	where would we have to land in order to tie that player?

	This is a metric for "probability that I end up ahead of this player"

	=== Example ===

	Num puddings are [1, 0, 3, 1]
	Average number of puddings remaining to be seen: 3.5
	Calculating for first player

	deltas:                      [1, -2, 0]
	delta ranges:                [(-2.5, 4.5), (-3.5, 1.5), (-2.5, 2.5)]
	zero crossings:              [0.36, 0.79, 0.5]
	odds of beating each player: [0.64, 0.21, 0.5]

	Using this to calculate pudding odds:

	Odds of first place: 0.64 * 0.21 * 0.5 = 6.7%
	Odds of last palce: (1 - 0.64) * (1 - 0.21) * (1 - 0.5) = 0.36 * 0.79 * 0.5 = 14.2%

	=== Problems with this algorithm (TODO: make improvements) ===

	This is just based on a single average number remaining to be seen, not on the distribution of probabilities.
	Accounting for this is doable, but would be much slower to compute, which could be a bottleneck for recursive solver
	where we call this many many times.
	Could probably get around this by precomputing results for different combinations at ProbablisticScorer init.

	This doesn't account for ties in number of puddings/maki.
	This has the same solution as the previous problem: need to calculate distribution of discrete probabilities instead
	of float averages

	We're only looking at a pair of players at a time - there are other players also taking cards!
	Or in other words, we're treating these as independent variables, when they're not.
	The concept of "on a scale from I take them all to you take them all" is still generally valid.
	What isn't valid is assuming it's linear (ends are much less likely, because they also require no other player
	takes any pudding).
	An idea (another approximation) for how to account for the this:
	- Take zero crossing of some sort of nonlinear function (inverse sigmoid) instead of a straight line
	- Or take zero-X of line and then scale nonlinearly after (this might actually work out to the same thing? Need
		to figure this out)
	- If trying this, need to confirm sum of all probabilities is still 1
	- This still treats them as independent variables, although I suspect this approximation might be close enough?

	People aren't just randomly given pudding/maki, they choose whether to take them or not.
	The problem is, predicting other players' behaviors is very difficult - especially since this is about future
	rounds so we know almost nothing about what cards will be in play.
	But there are some states we could certainly account for - e.g. once someone has already clinched most,
	they're unlikely to take any more (unless they're forced to, or want to block someone else)

	Opportunity cost:

	This doesn't account for opportunity cost of playing this instead of another card.

	Normally that wouldn't be the responsibility of this sort of function - it would be up to the thing calling
	the ProbablisticScorer to account for that.
	But this just spits out a single average score number - it doesn't tell you how many future cards you have to play
	to hit that score.

	If we want to keep the responsibilities separate, then this would have to return a list of "average score if you
	play this many future puddings, as well as the likelihood you actually will get a chance to", and that gets
	complicated fast (both in logic as well as performance).
	It's probably much simpler to incorporate it here.

	If so, keep in mind the opportunity cost only affects the first place positive points, not the last place
	negative points.
	"""

	# TODO: average_num_yet_to_see needs to be a list, since it could vary per player

	my_count = counts[player_idx]

	if include_self_as_none:
		deltas = [
			(my_count - other_player_count) if (other_idx != player_idx) else None
			for other_idx, other_player_count in enumerate(counts)
		]
	else:
		deltas = [
			my_count - other_player_count
			for other_idx, other_player_count in enumerate(counts)
			if other_idx != player_idx
		]

	ret = []
	for delta in deltas:
		if delta is None:
			odds_of_beating_player =  None
		else:
			min_delta = delta - average_num_yet_to_see
			zero_x = -min_delta / (2 * average_num_yet_to_see)
			odds_of_beating_player = max(0.0, min(1.0, 1.0 - zero_x))
			if verbose:
				max_delta = min_delta + 2 * average_num_yet_to_see
				print(f'  {player_idx=}, delta range [{min_delta:.2f}, {max_delta:.2f}], {zero_x=:.2f}, {odds_of_beating_player=:.2f}')
		ret.append(odds_of_beating_player)

	return ret


class ProbablisticScorer:

	def __init__(self, player_state: PlayerState):

		common = player_state.common_game_state

		self.num_players = common.num_players
		self.deck_total_num_puddings = common.starting_deck_distribution[Card.Pudding]

		assert all(len(other.hand) == len(player_state.hand) for other in player_state.other_player_states)
		end_of_round = not len(player_state.hand)

		self.num_unseen_pudding = player_state.deck_dist[Card.Pudding]
		assert self.num_unseen_pudding >= 0

		# TODO: "average" can be confused with "per player"; rename these vars ("average_total"? "expected_value"?)

		if end_of_round:
			self.num_known_pudding_in_hands = 0
			self.num_known_maki_in_hands = 0

			self.num_unknown_cards_this_round = 0
			self.average_unknown_maki_in_hands = 0
			self.average_unknown_pudding_in_hands = 0

		else:
			other_hands = [other.hand for other in player_state.other_player_states]
			all_hands = [player_state.hand] + other_hands

			self.num_unknown_cards_this_round = sum(count_card(hand, Card.Unknown) for hand in other_hands)

			# TODO: need to distinguish which pudding/maki are in hands we will or won't actually see again vs won't
			# (and calculate this for each player, which makes this a list)
			# Also need to distinguish between if we're going to use this to score a possible end of round scenario (at which point we will know all puddings), or now
			self.num_known_pudding_in_hands = sum(count_card(hand, Card.Pudding) for hand in all_hands)

			self.num_known_maki_in_hands = sum(count_maki(hand) for hand in all_hands)

			# TODO: this logic isn't correct, these aren't independent probabilities
			# Might be close enough approximation though? (Especially given the other approximations made when calculating maki value)
			nums_maki = (player_state.deck_dist[Card.Maki1], player_state.deck_dist[Card.Maki2], player_state.deck_dist[Card.Maki3])
			cards_in_deck = common.num_cards_remaining_in_deck + self.num_unknown_cards_this_round
			self.average_unknown_maki_in_hands = float(
				num_cards_odds_average(
					cards_in_deck=cards_in_deck, this_card_in_deck=nums_maki[0], cards_dealing=self.num_unknown_cards_this_round) +
				2 * num_cards_odds_average(
					cards_in_deck=cards_in_deck, this_card_in_deck=nums_maki[1], cards_dealing=self.num_unknown_cards_this_round) +
				3 * num_cards_odds_average(
					cards_in_deck=cards_in_deck, this_card_in_deck=nums_maki[2], cards_dealing=self.num_unknown_cards_this_round)
			)

			self.average_unknown_pudding_in_hands = float(num_cards_odds_average(
				cards_in_deck=cards_in_deck, this_card_in_deck=self.num_unseen_pudding, cards_dealing=self.num_unknown_cards_this_round
			))

		if common.last_round:
			assert common.num_cards_to_be_dealt == 0

		self.num_cards_to_be_dealt = common.num_cards_to_be_dealt
		self.num_cards_remaining_in_deck = common.num_cards_remaining_in_deck

		if self.num_cards_to_be_dealt and self.num_unseen_pudding:
			# There may be more puddings dealt in future rounds
			self.average_num_pudding_future_rounds = num_cards_odds_average(
				cards_in_deck=common.num_cards_remaining_in_deck,
				this_card_in_deck=self.num_unseen_pudding,
				cards_dealing=self.num_cards_to_be_dealt,
			)
			assert 0 < self.average_num_pudding_future_rounds < self.num_unseen_pudding
		else:
			# There will not be any more puddings dealt in future rounds
			self.average_num_pudding_future_rounds = 0

	@staticmethod
	def _calculate_player_probablistic_pudding_score(
			num_puddings: Sequence[int],
			player_idx: int,
			average_num_pudding_yet_to_see: float,
			verbose = False,
			) -> float:

		if average_num_pudding_yet_to_see <= 0:
			raise ValueError(f'{average_num_pudding_yet_to_see=}')

		# delta_nums_puddings = [
		# 	other_pudding_count - num_puddings[player_idx]
		# 	for other_idx, other_pudding_count in enumerate(num_puddings)
		# 	if other_idx != player_idx
		# ]

		# first_place_odds = 1.0
		# last_place_odds = 1.0
		# for delta in delta_nums_puddings:
		# 	min_delta = delta - average_num_pudding_yet_to_see
		# 	zero_x = -min_delta / (2 * average_num_pudding_yet_to_see)
		# 	odds_of_beating_player = max(0.0, min(1.0, zero_x))
		# 	if verbose:
		# 		max_delta = min_delta + 2 * average_num_pudding_yet_to_see
		# 		print(f'  {player_idx=}, delta range [{min_delta:.2f}, {max_delta:.2f}], {zero_x=:.2f}, {odds_of_beating_player=:.2f}')
		# 	first_place_odds *= odds_of_beating_player
		# 	last_place_odds *= (1.0 - odds_of_beating_player)

		odds_of_beating_players = _delta_range_probabilities(
			counts=num_puddings, player_idx=player_idx, average_num_yet_to_see=average_num_pudding_yet_to_see, verbose=verbose)
		assert len(odds_of_beating_players) == len(num_puddings) - 1
		first_place_odds = prod(odds_of_beating_players)
		last_place_odds = prod(1.0 - val for val in odds_of_beating_players)

		assert 0 <= first_place_odds <= 1
		assert 0 <= last_place_odds <= 1

		score = 6 * (first_place_odds - last_place_odds)

		if verbose:
			# print(f'  {player_idx=}, {delta_nums_puddings=}, 1st: {100.0*first_place_odds:.1f}%, last: {100.0*last_place_odds:.1f}%, {score=:.2f}')
			print(f'  {player_idx=}, {num_puddings=}, odds: {container_to_str(odds_of_beating_players, "{:.2f}", type=float)}, 1st: {100.0*first_place_odds:.1f}%, last: {100.0*last_place_odds:.1f}%, {score=:.2f}')

		return score

	@staticmethod
	def _calculate_player_probablistic_maki_score(
			num_maki: Sequence[int],
			player_idx: int,
			average_num_maki_yet_to_see: float,
			verbose = False,
			) -> float:

		if average_num_maki_yet_to_see <= 0:
			raise ValueError(f'{average_num_maki_yet_to_see=}')

		# delta_nums_maki = [
		# 	other_pudding_count - num_maki[player_idx]
		# 	for other_idx, other_pudding_count in enumerate(num_maki)
		# 	if other_idx != player_idx
		# ]

		# Essentially the same concept as for Puddings (TODO: this has all the same flaws as for puddings)

		# odds_of_beating_players = []

		# for delta in delta_nums_maki:
		# 	min_delta = delta - average_num_maki_yet_to_see
		# 	zero_x = -min_delta / (2 * average_num_maki_yet_to_see)
		# 	odds_of_beating_player = max(0.0, min(1.0, zero_x))
		# 	if verbose:
		# 		max_delta = min_delta + 2 * average_num_maki_yet_to_see
		# 		print(f'  {player_idx=}, delta range [{min_delta:.2f}, {max_delta:.2f}], {zero_x=:.2f}, {odds_of_beating_player=:.2f}')
		# 	odds_of_beating_players.append(odds_of_beating_player)

		odds_of_beating_players = _delta_range_probabilities(
			counts=num_maki, player_idx=player_idx, average_num_yet_to_see=average_num_maki_yet_to_see, include_self_as_none=True, verbose=verbose)
		assert len(odds_of_beating_players) == len(num_maki)

		first_place_odds = prod(val for val in odds_of_beating_players if val is not None)

		second_place_odds = 0.0
		for other_player_idx, odds_of_beating_this_player in enumerate(odds_of_beating_players):
			if other_player_idx == player_idx:
				assert odds_of_beating_this_player is None
				continue
			assert odds_of_beating_this_player is not None

			odds_beating_all_players_besides_this_one = prod(
				odds
				for odds_idx, odds in enumerate(odds_of_beating_players)
				if odds_idx not in (player_idx, other_player_idx)
			)

			odds_this_player_wins = prod(
				_delta_range_probabilities(counts=num_maki, player_idx=other_player_idx, average_num_yet_to_see=average_num_maki_yet_to_see, verbose=False)
			)

			second_place_odds += odds_this_player_wins * odds_beating_all_players_besides_this_one

		assert \
			first_place_odds >= 0 and \
			second_place_odds >= 0 and \
			0 <= (first_place_odds + second_place_odds) <= 1, \
			f"{first_place_odds=} + {second_place_odds=}"

		score = 6*first_place_odds + 3*second_place_odds

		if verbose:
			# print(f'  {player_idx=}, {delta_nums_maki=}, 1st: {100.0*first_place_odds:.1f}%, 2nd: {100.0*second_place_odds:.1f}%, {score=:.2f}')
			print(f'  {player_idx=}, {num_maki=}, 1st: {100.0*first_place_odds:.1f}%, 2nd: {100.0*second_place_odds:.1f}%, {score=:.2f}')

		return score

	def end_of_round_score_puddings(
			self,
			num_puddings: Sequence[int],
			verbose = False,
			) -> list[Real]:
		# End of round, so we don't have to worry about puddings in hands
		return self._score_puddings(
			num_puddings=num_puddings,
			verbose=verbose,
			average_num_pudding_yet_to_see=self.average_num_pudding_future_rounds,
		)

	def _score_puddings(
			self,
			num_puddings: Sequence[int],
			average_num_pudding_yet_to_see: float,
			verbose = False,
			) -> list[Real]:

		assert len(num_puddings) == self.num_players

		if not average_num_pudding_yet_to_see:
			return scoring.score_puddings(num_puddings)

		min_pudding_count = min(num_puddings)
		max_pudding_count = max(num_puddings)
		if min_pudding_count == max_pudding_count:
			return [0] * len(num_puddings)

		probablistic_scores = [
			self._calculate_player_probablistic_pudding_score(
				num_puddings=num_puddings,
				player_idx=player_idx,
				average_num_pudding_yet_to_see=average_num_pudding_yet_to_see,
				verbose=verbose)
			for player_idx in range(self.num_players)
		]

		assert len(probablistic_scores) == len(num_puddings)
		# TODO: These should sum to zero, but don't due to the approximations in _calculate_player_probablistic_pudding_score
		# assert isclose(probablistic_sum := sum(probablistic_scores), 0.0), f"Sum of probablistic scores non-zero: {probablistic_sum}"

		if verbose:
			print(f'probablistic_scores={container_to_str(probablistic_scores, "{:.2f}")}')

		return probablistic_scores

	def _score_maki(
			self,
			num_maki: Sequence[int],
			average_num_maki_yet_to_see: float,
			verbose = False,
			) -> list[Real]:

		# FIXME: see above
		if average_num_maki_yet_to_see is None:
			average_num_maki_yet_to_see = self.num_known_maki_in_hands + self.average_unknown_maki_in_hands

		assert len(num_maki) == self.num_players

		if not average_num_maki_yet_to_see:
			return scoring.score_maki(num_maki)

		min_maki_count = min(num_maki)
		max_maki_count = max(num_maki)
		if min_maki_count == max_maki_count:
			num_players = len(num_maki)
			return [6 // num_players] * num_players

		probablistic_scores = [
			self._calculate_player_probablistic_maki_score(
				num_maki=num_maki,
				player_idx=player_idx,
				average_num_maki_yet_to_see=average_num_maki_yet_to_see,
				verbose=verbose)
			for player_idx in range(self.num_players)
		]

		assert len(probablistic_scores) == len(num_maki)

		if verbose:
			print(f'probablistic_scores={container_to_str(probablistic_scores, "{:.2f}")}')

		return probablistic_scores

	def pudding_value(self, curr_num_puddings: Sequence[int]) -> list[Real]:
		"""
		Determine value of taking a pudding

		:returns: [
			average points this is worth for us (>= 0),
			average points we'd be blocking next player (usually <= 0, but not always),
			average points we'd be blocking player after that (usually <= 0, but not always),
			...
		]

		:details:
		Uses score_puddings() internally - calculates the differnce in scores between if we take this vs if we don't
		That means this has all the same flaws as score_puddings()
		"""

		assert len(curr_num_puddings) == self.num_players

		new_num_puddings = [curr_num_puddings[0] + 1] + [n for n in curr_num_puddings[1:]]
		assert len(new_num_puddings) == len(curr_num_puddings)

		debug_verbose = False  # DEBUG
		# debug_verbose = True  # DEBUG

		average_num_pudding_yet_to_see = self.average_num_pudding_future_rounds + self.num_known_pudding_in_hands + self.average_unknown_pudding_in_hands
		assert average_num_pudding_yet_to_see >= 1
		# assert average_num_pudding_yet_to_see >= 0
		# e.g. this can be 0.4, which means "there's 1 pudding out there but we're guessing it's not in this round"
		# if we're looking at it, then clearly it's in this round
		# FIXME: No, this shouldn't be possible! Puddings in hands should add! I think we should be adding self.num_known_pudding_in_hands
		# average_num_pudding_yet_to_see = max(average_num_pudding_yet_to_see, 1)

		scores_before = self._score_puddings(num_puddings=curr_num_puddings, average_num_pudding_yet_to_see=average_num_pudding_yet_to_see, verbose=debug_verbose)
		scores_after = self._score_puddings(num_puddings=new_num_puddings, average_num_pudding_yet_to_see=(average_num_pudding_yet_to_see - 1), verbose=debug_verbose)

		# TODO: might be useful to the thing calling this to know guaranteed points vs average points
		# i.e. does this guarantee exclusive 1st place or tie for 1st, or is it entirely probability based?
		# A few very simple checks could catch a lot of situations, e.g. if scores_after[0] == 6 and scores_before[0] != 6
		# Generalizing this would be a bit tougher though

		deltas = [after - before for before, after in zip(scores_before, scores_after)]

		if debug_verbose:  # DEBUG
			print(f'Known pudding in hands: {self.num_known_pudding_in_hands}')
			print('Unknown cards this round: %s, to be dealt: %s, in deck: %s, total unseen: %s' % (
				self.num_unknown_cards_this_round,
				self.num_cards_to_be_dealt,
				self.num_cards_remaining_in_deck,
				self.num_cards_remaining_in_deck + self.num_unknown_cards_this_round,
			))
			print(f'Remaining puddings odds: average {average_num_pudding_yet_to_see:.2f}')
			print(f'Puddings before: {curr_num_puddings} = {container_to_str(scores_before, "{:.2g}", type=float)}')
			print(f'Puddings after:  {new_num_puddings} = {container_to_str(scores_after, "{:.2g}", type=float)}')
			print(f'Deltas: {container_to_str(deltas, type=float)}')
			exit(1)

		return deltas

	def maki_value(self, card: Card, curr_num_maki: Sequence[int]) -> list[Real]:
		"""
		Determine value of taking a pudding

		:returns: [
			average points this is worth for us (>= 0),
			average points we'd be blocking next player (usually <= 0, but not always),
			average points we'd be blocking player after that (usually <= 0, but not always),
			...
		]

		:details:
		Uses score_puddings() internally - calculates the differnce in scores between if we take this vs if we don't
		That means this has all the same flaws as score_puddings()
		"""

		card_num_maki = card.num_maki()
		if not card_num_maki:
			raise ValueError(f'Card is not Maki: {card}')

		assert len(curr_num_maki) == self.num_players

		new_num_maki = [curr_num_maki[0] + card_num_maki] + [n for n in curr_num_maki[1:]]
		assert len(new_num_maki) == len(curr_num_maki)

		debug_verbose = False  # DEBUG

		assert self.num_known_maki_in_hands >= card_num_maki
		average_num_maki_yet_to_see = self.num_known_maki_in_hands + self.average_unknown_maki_in_hands
		

		scores_before = self._score_maki(num_maki=curr_num_maki, average_num_maki_yet_to_see=average_num_maki_yet_to_see, verbose=debug_verbose)
		scores_after = self._score_maki(num_maki=new_num_maki, average_num_maki_yet_to_see=(average_num_maki_yet_to_see - card_num_maki), verbose=debug_verbose)
		assert all(val >= 0 for val in scores_before)
		assert all(val >= 0 for val in scores_after)

		# TODO: as with pudding, might be useful to the thing calling this to know guaranteed points vs average points

		deltas = [after - before for before, after in zip(scores_before, scores_after)]

		if debug_verbose:  # DEBUG
			print(f'Known maki in hands: {self.num_known_maki_in_hands}')
			print('Unknown cards this round: %s, to be dealt: %s, in deck: %s, total unseen: %s' % (
				self.num_unknown_cards_this_round,
				self.num_cards_to_be_dealt,
				self.num_cards_remaining_in_deck,
				self.num_cards_remaining_in_deck + self.num_unknown_cards_this_round,
			))
			# print(f'Remaining maki odds: average {self.average_unknown_maki_in_hands:.2f}, distribution {container_to_str(self.remaining_maki_distribution, "{:.2f}", type=float)}')
			print(f'Average unknown maki: {self.average_unknown_maki_in_hands:.2f}')
			print(f'Maki before: {curr_num_maki} = {container_to_str(scores_before, "{:.2g}", type=float)}')
			print(f'Maki after:  {new_num_maki} = {container_to_str(scores_after, "{:.2g}", type=float)}')
			print(f'Deltas: {container_to_str(deltas, type=float)}')
			exit(1)

		return deltas

