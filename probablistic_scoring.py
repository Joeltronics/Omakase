#!/usr/bin/env python

from collections.abc import Sequence
from fractions import Fraction
from math import comb, isclose
from typing import List

from cards import Card
from player import PlayerState
import scoring


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


def num_cards_odds_list(
		cards_in_deck: int,
		this_card_in_deck: int,
		cards_dealing: int,
		) -> List[Fraction]:
	"""
	If I have a deck with cards_in_deck cards, and this_card_in_deck are card "X",
	and I deal cards_dealing cards, what are the odds we will get exactly N "X" cards?
	"""
	total_possible_hands = _total_possible_hands(cards_in_deck=cards_in_deck, cards_dealing=cards_dealing)
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


class ProbablisticScorer:

	def __init__(self, player_state: PlayerState):

		if player_state.any_unknown_cards:
			raise NotImplementedError('ProbablisticScorer does not currently work when there are unknown cards in current round')

		common = player_state.common_game_state

		self.num_players = common.num_players
		self.deck_total_num_puddings = common.starting_deck_distribution[Card.Pudding]

		self.num_cards_to_be_dealt = common.num_cards_to_be_dealt

		if common.last_round:
			assert self.num_cards_to_be_dealt == 0

		self.num_cards_remaining_in_deck = common.num_cards_remaining_in_deck

		self.pct_remaining_deck_to_see = self.num_cards_to_be_dealt / self.num_cards_remaining_in_deck
		assert 0.0 <= self.pct_remaining_deck_to_see < 1.0

		self.num_remaining_pudding = player_state.deck_dist[Card.Pudding]
		assert self.num_remaining_pudding >= 0

		if (not self.num_remaining_pudding) or (not self.num_cards_to_be_dealt):
			self.remaining_puddings_odds = [1.0]
			self.average_num_pudding_yet_to_see = 0
		else:
			self.remaining_puddings_odds = num_cards_odds_list(
				cards_in_deck=common.num_cards_remaining_in_deck,
				this_card_in_deck=self.num_remaining_pudding,
				cards_dealing=self.num_cards_to_be_dealt,
			)
			assert sum(self.remaining_puddings_odds) == 1
			self.average_num_pudding_yet_to_see = float(sum(
				num_pudding * probability for num_pudding, probability in enumerate(self.remaining_puddings_odds)
			))
			assert 0 < self.average_num_pudding_yet_to_see < self.num_remaining_pudding, f"{self.average_num_pudding_yet_to_see=}, {self.num_remaining_pudding=}, {self.remaining_puddings_odds=}"

	def _calculate_player_probablistic_pudding_score(
			self,
			num_puddings: Sequence[int],
			player_idx: int,
			) -> float:
		"""
		Calculate probablistic pudding score for this player

		Based on current number of puddings and number of puddings left,
		answer "what are the chances this player ends the game with the most or least?"

		This is a very simplified approximation, but it does an okay job (at least for rounds besides the final one,
		where this isn't used)

		=== Details ===

		Compare our number of puddings to each other player.
		Then, on a scale from "I take all remaining puddings" to "they take all remaining puddings",
		where would we have to land in order to tie that player?
		This is a metric for "odds that I end up ahead of this player"
		Then multiply the odds for all players

		=== Example ===

		Num puddings are [1, 0, 3, 1]
		Average number of puddings remaining to be seen: 3.5
		First player

		deltas:         [-1, 2, 0]
		delta ranges:   [(-4.5, 2.5), (-1.5, 3.5), (-2.5, 2.5)]
		zero crossings: [0.64 0.21, 0.5]

		odds of first place: 0.64 * 0.21 * 0.5 = 6.7%
		odds of last place: (1 - 0.64) * (1 - 0.21) * (1 - 0.5) = 0.46 * 0.79 * 0.5 = 18.2%

		So average point value of this state:
		6 * (0.067 - 0.182) = -0.69

		=== Problems with this algorithm (TODO) ===

		This is just based on a single average number of puddings remaining to be seen, not on the distribution of
		probabilities.
		Accounting for this is definitely doable, but would be much slower to compute, which could be a
		bottleneck for recursive solver where we call this many many times.
		Could probably get around this by precomputing results for different combinations at ProbablisticScorer init.

		This doesn't account for ties in number of puddings (this is essentially the same problem - need to calculate
		distribution of discrete probabilities instead of float averages)

		We're only looking at a pair of players at a time - there are other players also taking puddings!
		In practice these aren't actually independent variables.
		The concept of "on a scale from I take them all to you take them all" is still generally valid,
		What isn't valid is assuming it's linear (ends are much less likely, because they also require no other player
		takes any pudding).
		An ideas for how to account for the first problem:
		- Take zero crossing of some sort of nonlinear function (inverse sigmoid) instead of a straight line
		- Or take zero-X of line and then scale nonlinearly after (this might actually work out to the same thing? Need
			to figure this out)
		- If trying this, need to confirm sum of all probabilities is still 1
		- This still treats them as independent variables, although I suspect this approximation might be close enough?

		People aren't just randomly given puddings, they choose whether to take them or not.
		The problem is, predicting other players' behaviors is very difficult - especially since this is about future
		rounds so we know almost nothing about what cards will be in play.
		But there are some states we could certainly account for - e.g. once someone has already clinched most puddings,
		they're unlikely to take any more (only they're forced to, or want to block someone else)

		Opportunity cost:

		This doesn't account for opportunity cost of playing a pudding instead of another card.

		Normally that wouldn't be the responsibility of this sort of function - it would be up to the thing calling
		the ProbablisticScorer to account for that. But this just spits out a single average score number - it
		doesn't tell you how many future cards you have to play to hit that score.

		If we want to keep the responsibilities separate, then this would have to return a list of "average score if you
		play this many future puddings, as well as the likelihood you actually will get a chance to", and that gets
		complicated fast (both in logic as well as performance).
		It's probably much simpler to incorporate it here.

		If so, keep in mind the opportunity cost only affects the first place positive points, not the last place
		negative points.
		"""

		delta_nums_puddings = [
			num_puddings[player_idx] - other_pudding_count
			for other_idx, other_pudding_count in enumerate(num_puddings)
			if other_idx != player_idx
		]

		first_place_odds = 1.0
		last_place_odds = 1.0
		for delta in delta_nums_puddings:
			min_delta = delta - self.average_num_pudding_yet_to_see
			zero_x = -min_delta / (2 * self.average_num_pudding_yet_to_see)
			odds_of_beating_player = max(0.0, min(1.0, zero_x))
			first_place_odds *= odds_of_beating_player
			last_place_odds *= (1.0 - odds_of_beating_player)

		return 6 * (first_place_odds - last_place_odds)

	def score_puddings(self, num_puddings: Sequence[int]) -> List[int]:

		assert len(num_puddings) == self.num_players

		if (not self.num_cards_to_be_dealt) or (not self.num_remaining_pudding):
			return scoring.score_puddings(num_puddings)

		min_pudding_count = min(num_puddings)
		max_pudding_count = max(num_puddings)
		if min_pudding_count == max_pudding_count:
			return [0] * len(num_puddings)

		probablistic_scores = [
			self._calculate_player_probablistic_pudding_score(
				num_puddings=num_puddings,
				player_idx=player_idx)
			for player_idx in range(self.num_players)
		]

		assert len(probablistic_scores) == len(num_puddings)
		# assert isclose(probablistic_sum := sum(probablistic_scores), 0.0), f"Sum of probablistic scores non-zero: {probablistic_sum}"
		return probablistic_scores
