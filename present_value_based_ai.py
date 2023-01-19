#!/usr/bin/env python

from collections.abc import Collection, Sequence
from copy import copy, deepcopy
from dataclasses import dataclass
from numbers import Real
from typing import Optional, Tuple, Union
import warnings

from player import PlayerInterface, PlayerState
from probablistic_scoring import ProbablisticScorer, num_cards_odds_at_least
from cards import Card, Pick, Plate, card_names
from utils import *
import random


"""
If we could perfectly predict if one of our card picks would block someone else with a card pick, then we could
calculate exactly how many relative points it's worth for us.

But in practice, there are a ton of flaws with this:

* The blocking points calculating logic here is extremely simplistic, not going to be very accurate

* This logic doesn't factor in who we're blocking - it only calculates relative to the average score of all other
  players. In practice, we care a lot more about blocking players we're near in points than players we're not.

* Even with perfect logic, we don't know what cards the other player is actually going to pick

So because there's much more uncertainty in blocked points than in our points, weight blocked points significantly lower
"""
DEFAULT_BLOCKING_POINT_SCALE = 0.25


@dataclass
class CardPointsBreakdown:

	points_now: int = 0
	avg_future_points: Real = 0

	rel_points_blocking_per_player: Optional[Real] = None
	avg_opportunity_cost: Real = 0

	num_other_players: Optional[int] = None

	blocking_points_scale: Optional[float] = None
	opportunity_cost_scale: Optional[float] = None

	@property
	def avg_points_me(self) -> Real:
		return self.points_now + self.avg_future_points

	@property
	def avg_rel_points_blocking(self) -> float:
		if self.num_other_players is None:
			raise ValueError('num_other_players is not set')
		if self.rel_points_blocking_per_player is None:
			raise ValueError('rel_points_blocking_per_player is not set')
		return self.rel_points_blocking_per_player / self.num_other_players

	@property
	def total(self) -> float:
		opportunity_scale = self.opportunity_cost_scale if self.opportunity_cost_scale is not None else 1.0
		if self.rel_points_blocking_per_player:
			# avg_rel_points_blocking will throw if num_other_players or rel_points_blocking_per_player is unset
			blocking_scale = self.blocking_points_scale if self.blocking_points_scale is not None else 1.0
			return self.avg_points_me + blocking_scale*self.avg_rel_points_blocking - opportunity_scale*self.avg_opportunity_cost
		else:
			return self.avg_points_me + opportunity_scale*self.avg_opportunity_cost

	def __add__(self, other):

		def _match(name):
			mine = getattr(self, name)
			others = getattr(other, name)
			if (mine is not None) and (others is not None) and (mine != others):
				raise ValueError(f'Cannot add different CardPointsBreakdown with different {name} ({mine} vs {others})')
			return mine if mine is not None else others

		def _add_optional(a, b):
			if (a is None) and (b is None):
				return None
			else:
				return (a or 0) + (b or 0)

		return CardPointsBreakdown(
			points_now=self.points_now + other.points_now,
			avg_future_points=self.avg_future_points + other.avg_future_points,
			rel_points_blocking_per_player=_add_optional(self.rel_points_blocking_per_player, other.rel_points_blocking_per_player),
			avg_opportunity_cost=self.avg_opportunity_cost + other.avg_opportunity_cost,
			num_other_players=_match('num_other_players'),
			blocking_points_scale=_match('blocking_points_scale'),
			opportunity_cost_scale=_match('opportunity_cost_scale'),
		)

	def __str__(self) -> str:

		s = f'{self.total:.2f} = '

		if self.points_now:
			s += f'({self.points_now} now)'

		if self.avg_future_points:
			if self.points_now:
				s += ' + '
			s += f'({self.avg_future_points:.2f} future)'

		if self.avg_rel_points_blocking:
			s += ' + '
			if self.blocking_points_scale is not None and self.blocking_points_scale != 1.0:
				s += f'{self.blocking_points_scale:.2g}*'
			s += f'({self.rel_points_blocking_per_player:.2f} blocking)'
			if self.num_other_players != 1:
				s += f'/{self.num_other_players}'

		if self.avg_opportunity_cost:
			s += ' - '
			if self.opportunity_cost_scale is not None and self.opportunity_cost_scale != 1.0:
				s += f'{self.opportunity_cost_scale:.2g}*'
			s += f'({self.avg_opportunity_cost:.2f} opportunity)'

		return s


def _calculate_card_rate(player_state: PlayerState, card: Card, after_this_one: bool) -> float:
	"""
	:param after_this_one: If we're currently looking at 1 and looking to calculate the card rate after this one
	"""

	remaining_cards = len(player_state.hand) * player_state.get_num_players()
	num_this_card = 0
	num_unknown = 0
	for hand in player_state.hands:
		remaining_cards += len(hand)
		for this_card in hand:
			if this_card == card:
				num_this_card += 1
			if this_card == card:
				num_unknown += 1

	if after_this_one:
		assert remaining_cards >= 1
		assert num_this_card >= 1

	sub = 1 if after_this_one else 0

	if not num_unknown:
		ret = (num_this_card - sub) / (remaining_cards - sub)
		assert 0 <= ret <= 1
		return ret

	num_unseen_this_card = player_state.deck_dist[card]
	num_unseen_total = sum(player_state.deck_dist.values())
	unknown_this_card_rate = num_unseen_this_card / num_unseen_total
	assert 0.0 <= unknown_this_card_rate <= 1.0
	# TODO: use probablistic_scoring.num_cards_odds_average() instead
	avg_unknown_this_card = num_unknown * unknown_this_card_rate
	ret = (num_this_card + avg_unknown_this_card - sub) / (remaining_cards - sub)
	assert 0 <= ret <= 1
	return ret


def _sashimi_avg_points(
		num_cards_in_hand: int,
		player_state: Optional[PlayerState] = None,
		plate: Optional[Plate] = None,
		num_chopsticks: Optional[int] = None,
		) -> CardPointsBreakdown:

	assert num_cards_in_hand > 0

	if (player_state is None) and (plate is None):
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# TODO: factor in num_cards_in_hand?
		return CardPointsBreakdown(avg_future_points=3)

	if player_state is not None:
		plate = player_state.plate
		num_chopsticks = player_state.plate.chopsticks

	num_sashimi_needed = plate.num_sashimi_needed

	if num_sashimi_needed > num_cards_in_hand:
		return CardPointsBreakdown(0)

	if num_sashimi_needed == 1:
		# If this one completes a set, then this is straight-up 10 points, no further calculations needed
		return CardPointsBreakdown(10)

	num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	# Determine what percentage of remaining cards are Sashimi

	if player_state is None:
		# 14/108 cards are Sashimi = 13%, and we've already seen 1 (this one), plus any others already on plate
		sashimi_rate = (14 - (1 + plate.unscored_sashimi)) / (108 - (1 + plate.unscored_sashimi))
	else:
		sashimi_rate = _calculate_card_rate(player_state=player_state, card=Card.Sashimi, after_this_one=True)

	assert 0.0 <= sashimi_rate <= 1.0

	# Now calculate odds & value

	# TODO: this is a bad approximation; should use probablistic_scoring.num_cards_odds_at_least() instead
	# that's not totally straight-forward though, because we could see the same hand multiple times

	if num_sashimi_needed == 2:
		# What are the odds we will see 1 more after this one?

		# 8-card game, turn 2, no player_state: 2.38
		avg_num_sashimi_yet_to_see = num_cards_yet_to_see * sashimi_rate

		# Right now (before we've sunk the cost), this one card is only worth half the 10 points
		# 8-card game, turn 2, no player_state: 5 points
		avg_future_points = (10/2) * min(1.0, avg_num_sashimi_yet_to_see)
		return CardPointsBreakdown(avg_future_points=avg_future_points)

	elif num_sashimi_needed == 3:
		# What are the odds we will see 2 more? (on 2 separate hands, unless num_chopsticks)

		# 8-card game, turn 1, no player_state: 3.4
		# 8-card game, turn 2, no player_state: 2.55
		avg_num_sashimi_yet_to_see = num_cards_yet_to_see * sashimi_rate

		# The number of cards we'll actually see is some sort of distribution with a mean of that number,
		# but the actual distribution is going to have skew
		# Very very very rough approximation, just divide by 2 and that's the odds that we'll see 2
		if num_chopsticks:
			# TODO: account that maybe we've already used chopsticks before getting to this point (if num_chopsticks == 1)
			odds_seeing_2_sashimi = 0.5 * avg_num_sashimi_yet_to_see
		else:
			# Even rougher approximation, subtract 0.1 to adjust for odds they could both be on same turn
			odds_seeing_2_sashimi = 0.4 * avg_num_sashimi_yet_to_see

		# Scale by 90% to adjust for probability we would actually take the 2nd sashimi (3rd is considered a sure thing)

		# 8-card game, turns 1-2, no player_state: 3 points (regardless of chopsticks)
		avg_future_points = (10/3) * min(1.0, odds_seeing_2_sashimi) * 0.9
		return CardPointsBreakdown(avg_future_points=avg_future_points)

	else:
		raise AssertionError(f'invalid {num_sashimi_needed=}')


def _tempura_avg_points(
		num_cards_in_hand: int,
		player_state: Optional[PlayerState] = None,
		plate: Optional[Plate] = None,
		) -> CardPointsBreakdown:

	assert num_cards_in_hand > 0

	if (player_state is None) and (plate is None):
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# TODO: factor in num_cards_in_hand?
		return CardPointsBreakdown(avg_future_points=2)

	if player_state is not None:
		plate = player_state.plate

	num_tempura_needed = plate.num_tempura_needed

	if num_tempura_needed > num_cards_in_hand:
		return CardPointsBreakdown(0)

	if num_tempura_needed == 1:
		return CardPointsBreakdown(5)

	if num_tempura_needed != 2:
		raise AssertionError(f"Invalid {num_tempura_needed=}")

	num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	# Determine what percentage of remaining cards are Tempura

	if player_state is None:
		tempura_rate = 13/107
	else:
		tempura_rate = _calculate_card_rate(player_state=player_state, card=Card.Tempura, after_this_one=True)

	assert 0.0 <= tempura_rate <= 1.0

	# 8-card game, turn 1, no player_state: 3.4
	avg_num_tempura_yet_to_see = num_cards_yet_to_see * tempura_rate
	avg_future_points =  (5/2) * min(1.0, avg_num_tempura_yet_to_see)
	return CardPointsBreakdown(avg_future_points=avg_future_points)


def _wasabi_avg_points(*,
		num_cards_in_hand: int,
		player_state: Optional[PlayerState] = None,
		num_unused_wasabi: Optional[int] = None,
		) -> CardPointsBreakdown:
	if player_state is not None:
		# TODO BPV: return _wasabi_avg_points_full_state(player_state)
		return _wasabi_avg_points(num_cards_in_hand=num_cards_in_hand, num_unused_wasabi=player_state.plate.unused_wasabi, player_state=None)

	elif num_unused_wasabi is not None:
		# 8-card game, turn 1: worth 3.5 points
		# 8-card game, turn 2: worth 3 points, or 1.5 if we already have wasabi
		avg_future_points = min((num_cards_in_hand - 1) / (2 ** (1 + num_unused_wasabi)), 6)
		return CardPointsBreakdown(avg_future_points=avg_future_points)

	else:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# There's a chance another player could have unused wasabi, hence 2.1 instead of 2
		return CardPointsBreakdown(avg_future_points=min((num_cards_in_hand - 1) / 2.1, 6))


def _wasabi_avg_points_full_state(player_state: PlayerState) -> CardPointsBreakdown:
	raise NotImplementedError()  # TODO BPV


def _nigiri_opportunity_cost(
		card: Card,
		*,
		num_cards_in_hand: int,
		player_state: Optional[PlayerState] = None,
		num_unused_wasabi: Optional[int] = None,
		) -> Real:

	assert card.is_nigiri()

	# If this is a squid, then we can't possibly do better; no opportunity cost
	if card not in [Card.EggNigiri, Card.SalmonNigiri]:
		return 0.0

	elif player_state is not None:
		# TODO BPV: return _nigiri_opportunity_cost_full_state(card, player_state)
		return _nigiri_opportunity_cost_plate(card, num_cards_in_hand=num_cards_in_hand, num_unused_wasabi=player_state.plate.unused_wasabi)

	elif num_unused_wasabi is not None:
		return _nigiri_opportunity_cost_plate(card, num_cards_in_hand=num_cards_in_hand, num_unused_wasabi=num_unused_wasabi)

	else:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# TODO: what to count for this?
		return 0


def _nigiri_opportunity_cost_plate(
		card: Card,
		*,
		num_cards_in_hand: int,
		num_unused_wasabi: int,
		) -> Real:

	assert card in [Card.EggNigiri, Card.SalmonNigiri]
	assert num_unused_wasabi >= 0

	# If there's no unused wasabi, then no opportunity cost
	if not num_unused_wasabi:
		return 0

	# Likelihood we will get a better nigiri later, and the opportunity cost of using up the Wasabi now
	num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	# 8-card game, turn 2: 0.97
	avg_num_squid_yet_to_see = num_cards_yet_to_see * 5 / 108

	if card == Card.SalmonNigiri:
		# 5 / 108 cards are squid, better by 3 points
		# Assume there's a 95% chance we would take it if we see it
		return min(1.0, avg_num_squid_yet_to_see) * 3.0 * 0.95

	elif card == Card.EggNigiri:
		# 5 / 108 cards are squid, assume 95% chance would take it if we see it
		avg_num_squid_yet_to_see = num_cards_yet_to_see * 5 / 108
		odds_taking_squid = min(1.0, avg_num_squid_yet_to_see) * 0.95

		# 10 / 108 cards are salmon, assume 75% chance would take it if we see it
		# 8-card game, turn 2: 1.94
		avg_num_salmon_yet_to_see = num_cards_yet_to_see * 10 / 108
		# TODO: subtraction isn't quite correct here, because the order we see them matters
		# Might be a close enough approximation though
		odds_taking_salmon = max(min(1.0, avg_num_salmon_yet_to_see) * 0.75 - odds_taking_squid, 0.0)

		return 6 * odds_taking_squid + 3 * odds_taking_salmon

	else:
		raise AssertionError(repr(card))


def _nigiri_opportunity_cost_full_state(card: Card, player_state: PlayerState) -> CardPointsBreakdown:
	assert card in [Card.EggNigiri, Card.SalmonNigiri]
	raise NotImplementedError()  # TODO BPV


def _nigiri_avg_points(
		card: Card,
		*,
		num_cards_in_hand: int,
		player_state: Optional[PlayerState] = None,
		num_unused_wasabi: Optional[int] = None,
		) -> CardPointsBreakdown:

	assert card.is_nigiri()

	avg_opportunity_cost = _nigiri_opportunity_cost(
		card,
		player_state=player_state,
		num_unused_wasabi=num_unused_wasabi,
		num_cards_in_hand=num_cards_in_hand)

	if num_unused_wasabi is None:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# Estimate 10% chance the player has Wasabi out
		wasabi_scale = (3 * 0.1) + (1 * 0.9)
	elif num_unused_wasabi:
		wasabi_scale = 3
	else:
		wasabi_scale = 1

	if card == Card.SquidNigiri:
		return CardPointsBreakdown(3*wasabi_scale, avg_opportunity_cost=avg_opportunity_cost)

	if card == Card.SalmonNigiri:
		return CardPointsBreakdown(2*wasabi_scale, avg_opportunity_cost=avg_opportunity_cost)

	if card == Card.EggNigiri:
		return CardPointsBreakdown(wasabi_scale, avg_opportunity_cost=avg_opportunity_cost)

	raise KeyError(repr(card))


def _maki_avg_points(
		card: Card,
		*,
		num_players: int,
		player_state: Optional[PlayerState] = None,
		probablistic_scorer: Optional[ProbablisticScorer] = None,
		) -> CardPointsBreakdown:

	assert card.is_maki()

	avg_future_points = None

	if player_state is not None:
		# TODO BPV: enable this; it doesn't seem to work properly
		# assert probablistic_scorer is not None
		# return _maki_avg_points_full_state(card=card, player_state=player_state, probablistic_scorer=probablistic_scorer)
		return _maki_avg_points(card=card, num_players=num_players)

	if card == Card.Maki3:
		return CardPointsBreakdown(avg_future_points=(4.5 / num_players))
	
	if card == Card.Maki2:
		return CardPointsBreakdown(avg_future_points=(3.0 / num_players))
	
	if card == Card.Maki1:
		return CardPointsBreakdown(avg_future_points=(1.5 / num_players))
	
	if avg_future_points is None:
		raise KeyError(repr(card))


def _maki_avg_points_full_state(card: Card, player_state: PlayerState, probablistic_scorer: ProbablisticScorer) -> CardPointsBreakdown:

	assert card.is_maki()

	curr_num_maki = [p.plate.maki for p in player_state.public_states]

	maki_value = probablistic_scorer.maki_value(card, curr_num_maki=curr_num_maki)

	avg_future_points = maki_value[0]
	rel_points_blocking_per_player = -sum(maki_value[1:])

	# TODO: as with pudding, if this clinches, some avg_future_points can instead be classified as points_now
	return CardPointsBreakdown(
		avg_future_points=avg_future_points,
		rel_points_blocking_per_player=rel_points_blocking_per_player,
	)


def _dumpling_avg_points(*,
		num_cards_in_hand: int,
		player_state: Optional[PlayerState] = None,
		plate: Optional[Plate] = None,
		) -> CardPointsBreakdown:

	if (player_state is None) and (plate is None):
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		return CardPointsBreakdown(avg_future_points=2)

	if player_state is not None:
		plate = player_state.plate

	# If already 5 dumplings, there's no point taking any more
	if plate.dumplings >= 5:
		return CardPointsBreakdown(0)

	points_this_dumpling = plate.dumplings + 1

	# Taking a dumpling now also makes future dumplings more valuable
	# How many more dumplings are we expected to see?
	num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	if player_state is None:
		dumpling_rate = 13/107
	else:
		dumpling_rate = _calculate_card_rate(player_state, Card.Dumpling, after_this_one=True)

	# 14/108 cards are Dumplings = 13%
	# 8-card hand, turn 1: 3.4
	avg_num_dumplings_yet_to_see = num_cards_yet_to_see * dumpling_rate

	# Of course, these potential points are only valid if we actually take the dumplings
	# How many of these are we likely to actually take?
	# As a very rough guess, assume we'll take half
	avg_num_dumplings_yet_to_take = 0.5*avg_num_dumplings_yet_to_see

	# No points if we take more than 5 total
	max_num_dumplings_left_to_make = max(0, 4 - plate.dumplings)
	avg_num_dumplings_yet_to_take = min(avg_num_dumplings_yet_to_take, max_num_dumplings_left_to_make)

	# This makes them each more valuable by 1 point
	avg_points_future_dumplings = avg_num_dumplings_yet_to_take

	# 8-card game, turn 1: 1 + 1.7 = 2.7
	return CardPointsBreakdown(points_now=points_this_dumpling, avg_future_points=avg_points_future_dumplings)


def _pudding_avg_points(*,
		num_players: int,
		player_state: Optional[PlayerState] = None,
		probablistic_scorer: Optional[ProbablisticScorer] = None,
		) -> CardPointsBreakdown:

	if player_state is not None:
		assert probablistic_scorer is not None
		return _pudding_avg_points_full_state(player_state, probablistic_scorer)

	if num_players > 2:
		# 12 points total, across 3 rounds
		# 5-player: 0.8 points
		# 4-player: 1 point
		# 3-player: 1.33 points
		return CardPointsBreakdown(avg_future_points=(4 / num_players))
	else:
		# In 2-player, there's no -6, so 6 points total; worth 1 point
		return CardPointsBreakdown(avg_future_points=(2 / num_players))


def _pudding_avg_points_full_state(player_state: PlayerState, probablistic_scorer: ProbablisticScorer) -> CardPointsBreakdown:

	curr_num_puddings = [p.num_pudding for p in player_state.public_states]

	pudding_value = probablistic_scorer.pudding_value(curr_num_puddings)

	avg_future_points = pudding_value[0]
	rel_points_blocking_per_player = -sum(pudding_value[1:])

	# TODO: technically, if this clinches most pudding (or ties for it), some of the "future points" can be classified as points_now
	# Would likely need to handle this inside ProbablisticScorer
	# Currently it doesn't matter, because there's no difference in how we use points_now vs avg_future_points besides debugging
	return CardPointsBreakdown(
		avg_future_points=avg_future_points,
		rel_points_blocking_per_player=rel_points_blocking_per_player,
	)


def _chopsticks_avg_points(*,
		num_cards_in_hand: int,
		num_chopsticks: Optional[int] = None,
		player_state: Optional[PlayerState] = None,
		) -> CardPointsBreakdown:

	if player_state is not None:
		# TODO BPV: return _chopsticks_avg_points_full_state(player_state)
		return _chopsticks_avg_points_plate(num_cards_in_hand=num_cards_in_hand, num_chopsticks=player_state.plate.chopsticks)
	elif num_chopsticks is not None:
		return _chopsticks_avg_points_plate(num_cards_in_hand=num_cards_in_hand, num_chopsticks=num_chopsticks)
	else:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		num_remaining_turns_could_use_these_chopsticks = max(num_cards_in_hand - 2 - 1, 0)
		return CardPointsBreakdown(avg_future_points=(0.5 * num_remaining_turns_could_use_these_chopsticks))


def _chopsticks_avg_points_plate(*,
		num_cards_in_hand: int,
		num_chopsticks: int,
		) -> CardPointsBreakdown:

	assert num_chopsticks >= 0

	# If there are 3 cards in hand and 0 chopsticks on plate, there's 1 more turn we could use them
	num_remaining_turns_could_use_these_chopsticks = num_cards_in_hand - 2 - num_chopsticks

	if num_remaining_turns_could_use_these_chopsticks <= 0:
		return CardPointsBreakdown(0)

	# num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	# Guesstimate about 0.5 point per turn left? (Even worse if we already have chopsticks)
	# TODO: maybe a bit higher than this in early turns (before people have taken all the good stuff)
	points = (0.5 ** (num_chopsticks + 1)) * num_remaining_turns_could_use_these_chopsticks

	# TODO: slightly higher if we currently have 1 sashimi

	# 8-card game, turn 1: 3 points

	return CardPointsBreakdown(avg_future_points=points)


def _chopsticks_avg_points_full_state(player_state: PlayerState) -> CardPointsBreakdown:
	raise NotImplementedError()  # TODO BPV


def _using_chopsticks_opportunity_cost(*,
		num_chopsticks: int,
		num_cards_in_hand: int,
		player_state: Optional[PlayerState] = None,
		) -> Real:
	if player_state is not None:
		# TODO BPV: return _using_chopsticks_opportunity_cost_full_state(player_state, num_chopsticks=num_chopsticks)
		return _using_chopsticks_opportunity_cost_plate(num_chopsticks=num_chopsticks, num_cards_in_hand=num_cards_in_hand)
	else:
		return _using_chopsticks_opportunity_cost_plate(num_chopsticks=num_chopsticks, num_cards_in_hand=num_cards_in_hand)


def _using_chopsticks_opportunity_cost_plate(num_chopsticks: int, num_cards_in_hand: int) -> Real:

	# TODO: should wrap _chopsticks_avg_points()

	assert num_chopsticks >= 1

	# If there are 3 cards in hand and 1 chopsticks on plate, there's 2 more turns we could use them (after this one)
	num_remaining_turns_could_use_chopsticks = num_cards_in_hand - 2 - num_chopsticks

	if num_remaining_turns_could_use_chopsticks <= 0:
		return 0

	# 8-card game, turn 2, 1 chopsticks: 4 more turns could use them, 2 points
	# 8-card game, turn 3, 1 chopsticks: 3 more turns could use them, 1.5 point
	# 8-card game, turn 3, 2 chopsticks: 2 more turns could use them, 0.5 points
	cost = (0.5 ** num_chopsticks) * num_remaining_turns_could_use_chopsticks

	return cost


def _using_chopsticks_opportunity_cost_full_state(player_state: PlayerState, num_chopsticks: int) -> Real:
	assert num_chopsticks >= 1
	raise NotImplementedError()  # TODO BPV


def _avg_points_not_counting_blocking(
		card: Card,
		*,
		num_cards: int,
		num_players: int,
		player_state: Optional[PlayerState] = None,
		probablistic_scorer: Optional[ProbablisticScorer] = None,
		plate: Optional[Plate] = None,
		num_unused_wasabi: Optional[int] = None,
		num_chopsticks: Optional[int] = None,
		) -> CardPointsBreakdown:

	if card == Card.Sashimi:
		return _sashimi_avg_points(player_state=player_state, num_cards_in_hand=num_cards, plate=plate, num_chopsticks=num_chopsticks)

	if card == Card.Tempura:
		return _tempura_avg_points(player_state=player_state, num_cards_in_hand=num_cards, plate=plate)

	if card == Card.Dumpling:
		return _dumpling_avg_points(player_state=player_state, num_cards_in_hand=num_cards, plate=plate)

	if card == Card.Wasabi:
		return _wasabi_avg_points(player_state=player_state, num_cards_in_hand=num_cards, num_unused_wasabi=num_unused_wasabi)

	if card.is_nigiri():
		return _nigiri_avg_points(card, num_unused_wasabi=num_unused_wasabi, num_cards_in_hand=num_cards)

	if card.is_maki():
		return _maki_avg_points(card, player_state=player_state, probablistic_scorer=probablistic_scorer, num_players=num_players)

	if card == Card.Pudding:
		return _pudding_avg_points(player_state=player_state, probablistic_scorer=probablistic_scorer, num_players=num_players)
	
	if card == Card.Chopsticks:
		return _chopsticks_avg_points(player_state=player_state, num_chopsticks=num_chopsticks, num_cards_in_hand=num_cards)

	raise KeyError(repr(card))


def _card_avg_points(
		card: Card,
		*,
		plate: Optional[Plate],
		num_cards: int,
		num_players: int,
		num_unused_wasabi: Optional[int],
		num_chopsticks: Optional[int],
		player_state: Optional[PlayerState] = None,
		probablistic_scorer: Optional[ProbablisticScorer] = None,
		) -> CardPointsBreakdown:

	points = _avg_points_not_counting_blocking(
		card=card,
		num_cards=num_cards,
		num_players=num_players,
		player_state=player_state,
		probablistic_scorer=probablistic_scorer,
		plate=plate,
		num_unused_wasabi=num_unused_wasabi,
		num_chopsticks=num_chopsticks,
	)
	assert isinstance(points, CardPointsBreakdown), f"Did not return CardPointsBreakdown: _avg_points_not_counting_blocking({card=}, {num_cards=}, {num_players=}, {player_state=}, {plate=}, {num_unused_wasabi=}, {num_chopsticks=})"

	points.num_other_players = (num_players - 1)

	if points.rel_points_blocking_per_player is not None:
		return points

	avg_relative_points_from_blocking = _avg_points_not_counting_blocking(
		card=card,
		num_cards=num_cards,
		num_players=num_players,
		player_state=None,
		probablistic_scorer=None,
		plate=None,
		num_unused_wasabi=None,
		num_chopsticks=None,
	)
	assert isinstance(avg_relative_points_from_blocking, CardPointsBreakdown), f"Did not return CardPointsBreakdown: _avg_points_not_counting_blocking({card=}, {num_cards=}, {num_players=})"
	assert avg_relative_points_from_blocking.rel_points_blocking_per_player is None
	avg_relative_points_from_blocking = avg_relative_points_from_blocking.total

	points.rel_points_blocking_per_player = avg_relative_points_from_blocking

	return points


def _pair_avg_points(
		cards: Tuple[Card, Card],
		*,
		plate: Optional[Plate],
		num_cards: int,
		num_players: int,
		num_unused_wasabi: int,
		num_chopsticks: int,
		player_state: Optional[PlayerState] = None,
		probablistic_scorer: Optional[ProbablisticScorer] = None,
		) -> CardPointsBreakdown:

	assert num_cards >= 2
	assert num_chopsticks >= 1

	card1, card2 = cards
	num_chopsticks -= 1

	if player_state is not None:
		plate = player_state.plate

	"""
	FIXME: a lot of the assumptions in _card_avg_points() don't actually work with chopsticks!

	e.g. (Tempura, Tempura) will give current points as 5 (correct), but *also* indicate future points (wrong!)
	But we can't just naively delete avg_future_points from the first card - we don't know if they're still relevant or not.
	e.g. if we take (Tempura, Nigiri) then we shouldn't delete the avg_future_points from the Tempura!

	This will be an even bigger problem with player_state!

	Also, some cards use num_cards to determine average value, based on the probability later cards could be related.
	We already know if the next card is related or not!

	The existing logic should still be valid for pairs of independent cards.
	So we can probably fix this by adding special cases for pairs of related cards.

	Related pairs to worry about:
	- 2 sashimi (if we are currently at 0 or 1)
	- 2 tempura (if we are currently at 0)
	- 2 dumplings (if we are currently < 4)
	- wasabi + nigiri (only in that order)
	"""

	card1_points = _card_avg_points(
		card1,
		plate=plate,
		num_cards=num_cards,
		num_players=num_players,
		num_unused_wasabi=num_unused_wasabi,
		num_chopsticks=num_chopsticks,
		player_state=player_state,
		probablistic_scorer=probablistic_scorer,
	)

	if plate is not None:
		plate_after = copy(plate)
		plate_after.add(card1)
	else:
		plate_after = None

	if card1 == Card.Wasabi:
		num_unused_wasabi += 1
	
	if card1 == Card.Chopsticks:
		num_chopsticks += 1

	if player_state is not None:

		player_state = deepcopy(player_state)

		player_state.hand.remove(card1)
		player_state.hand.append(Card.Chopsticks)
		assert plate_after is not None
		player_state.public_state.plate = plate_after

		if probablistic_scorer is not None:
			probablistic_scorer = ProbablisticScorer(player_state)
		else:
			warnings.warn('player_state is not None, but probablistic_scorer is')

	card2_points = _card_avg_points(
		card2,
		plate=plate_after,
		num_cards=(num_cards - 1),
		num_players=num_players,
		num_unused_wasabi=num_unused_wasabi,
		num_chopsticks=num_chopsticks,
		player_state=player_state,
		probablistic_scorer=probablistic_scorer,
	)

	return card1_points + card2_points


"""
Simple AI that just tries to maximize points in the moment, without even looking at own plate
(except to know if it's possible to play chopsticks)
The only variable it looks at is how many cards are in the hand
"""
class HandOnlyAI(PlayerInterface):
	@staticmethod
	def get_name() -> str:
		return "HandOnlyAI"

	def __init__(
			self, *,
			blocking_point_scale: float = DEFAULT_BLOCKING_POINT_SCALE,
			opportunity_cost_scale: float = 1.0,
			chopstick_opportunity_cost: bool = True,
			always_take_chopsticks: bool = False,
			):
		self.blocking_point_scale = blocking_point_scale
		self.opportunity_cost_scale = opportunity_cost_scale
		self.always_take_chopsticks = always_take_chopsticks
		self.chopstick_opportunity_cost = chopstick_opportunity_cost

	def play_turn(self, player_state: PlayerState, verbose=False) -> Pick:
		return present_value_play_turn(
			player_state = None,
			hand = player_state.hand,
			plate = None,
			num_players = player_state.get_num_players(),
			blocking_point_scale=self.blocking_point_scale,
			opportunity_cost_scale=self.opportunity_cost_scale,
			always_take_chopsticks=self.always_take_chopsticks,
			chopstick_opportunity_cost=self.chopstick_opportunity_cost,
			has_chopsticks=bool(player_state.plate.chopsticks),
			has_wasabi=bool(player_state.plate.unused_wasabi),
			verbose=verbose,
		)


"""
Simple AI that just tries to maximize points in the moment
Only looks at what's on current plate and how many cards are left
Doesn't look at other players' hands/plates, or what other cards are still out there
Minimal regard for opportunity cost of future moves
"""
class TunnelVisionAI(PlayerInterface):
	@staticmethod
	def get_name() -> str:
		return "TunnelVisionAI"

	def __init__(
			self, *,
			blocking_point_scale: float = DEFAULT_BLOCKING_POINT_SCALE,
			opportunity_cost_scale: float = 1.0,
			chopstick_opportunity_cost: bool = True,
			always_take_chopsticks: bool = False,
			):
		self.blocking_point_scale = blocking_point_scale
		self.opportunity_cost_scale = opportunity_cost_scale
		self.always_take_chopsticks = always_take_chopsticks
		self.chopstick_opportunity_cost = chopstick_opportunity_cost

	def play_turn(self, player_state: PlayerState, verbose=False) -> Pick:
		return present_value_play_turn(
			player_state = None,
			hand = player_state.hand,
			plate = player_state.plate,
			num_players = player_state.get_num_players(),
			blocking_point_scale=self.blocking_point_scale,
			opportunity_cost_scale=self.opportunity_cost_scale,
			always_take_chopsticks=self.always_take_chopsticks,
			chopstick_opportunity_cost=self.chopstick_opportunity_cost,
			verbose=verbose,
		)


"""
Simple AI that just tries to maximize points in the moment, based on current plate, known hands, and average distribution of unknown cards
Only uses other hands for sake of distribution of remaining cards - makes no attempt to account for what cards others will actually play
Minimal regard for opportunity cost of future moves
"""
class BasicPresentValueAI(PlayerInterface):
	@staticmethod
	def get_name() -> str:
		return "BasicPresentValueAI"

	def __init__(
			self, *,
			blocking_point_scale: float = DEFAULT_BLOCKING_POINT_SCALE,
			opportunity_cost_scale: float = 1.0,
			chopstick_opportunity_cost: bool = True,
			always_take_chopsticks: bool = False,
			):
		self.blocking_point_scale = blocking_point_scale
		self.opportunity_cost_scale = opportunity_cost_scale
		self.always_take_chopsticks = always_take_chopsticks
		self.chopstick_opportunity_cost = chopstick_opportunity_cost

	def play_turn(self, player_state: PlayerState, verbose=False) -> Pick:
		return present_value_play_turn(
			player_state=player_state,
			hand=player_state.hand,
			blocking_point_scale=self.blocking_point_scale,
			opportunity_cost_scale=self.opportunity_cost_scale,
			always_take_chopsticks=self.always_take_chopsticks,
			chopstick_opportunity_cost=self.chopstick_opportunity_cost,
			verbose=verbose,
		)


def present_value_play_turn(*,
		player_state: Optional[PlayerState] = None,
		hand: Optional[Sequence[Card]] = None,  # Required if player_state is None
		plate: Optional[Plate] = None,
		num_players: Optional[int] = None,  # Required if player_state is None
		blocking_point_scale: float = DEFAULT_BLOCKING_POINT_SCALE,
		opportunity_cost_scale: float = 1.0,
		chopstick_opportunity_cost: bool = True,
		always_take_chopsticks: bool = False,
		verbose=False,
		has_chopsticks: Optional[bool] = None,  # Required if player_state & plate are None
		has_wasabi: Optional[bool] = None,  # Required if player_state & plate are None
		) -> Pick:

	probablistic_scorer = ProbablisticScorer(player_state) if (player_state is not None) else None

	if hand is None:
		if player_state is None:
			raise ValueError('Must provide hand if not providing player_state')
		hand = player_state.hand

	if num_players is None:
		if player_state is None:
			raise ValueError('Must provide num_players if not providing player_state')
		num_players = player_state.get_num_players()

	if plate is None and player_state is not None:
		plate = player_state.plate

	n_cards = len(hand)
	assert n_cards > 0

	if n_cards == 1:
		return Pick(hand[0])

	if plate is not None:
		num_chopsticks = plate.chopsticks
		num_unused_wasabi = plate.unused_wasabi
	else:
		if has_chopsticks is None or has_wasabi is None:
			raise ValueError('Must provide has_chopsticks & has_wasabi if plate is None')
		num_chopsticks = int(bool(has_chopsticks))
		num_unused_wasabi = int(bool(has_wasabi))

	can_use_chopsticks = num_chopsticks and len(hand) > 1

	# TODO: could make this slightly more efficient by eliminating some obvious picks (don't take lower nigiri or Maki)
	# Should just use utils.get_all_picks(), it has this logic built in
	cards_points = {
		Pick(card): _card_avg_points(
			card,
			player_state=player_state,
			probablistic_scorer=probablistic_scorer,
			plate=plate,
			num_cards=len(hand),
			num_players=num_players,
			num_unused_wasabi=num_unused_wasabi,
			num_chopsticks=num_chopsticks,
		) for card in set(hand)
	}

	if can_use_chopsticks:
		chopstick_opportunity_cost = _using_chopsticks_opportunity_cost(
			num_chopsticks=num_chopsticks,
			num_cards_in_hand=n_cards,
		) if chopstick_opportunity_cost else 0

		chopstick_picks = get_chopstick_picks(hand=hand, num_unused_wasabi=num_unused_wasabi)
		for chopstick_pick in chopstick_picks:
			points = _pair_avg_points(
					chopstick_pick.as_pair(),
					player_state=player_state,
					probablistic_scorer=probablistic_scorer,
					plate=plate,
					num_cards=len(hand),
					num_players=num_players,
					num_unused_wasabi=num_unused_wasabi,
					num_chopsticks=num_chopsticks,
			)
			points = points + CardPointsBreakdown(avg_opportunity_cost=chopstick_opportunity_cost)
			cards_points[chopstick_pick] = points

	# Add number of players & scale values

	for v in cards_points.values():
		v.num_other_players = num_players - 1
		v.blocking_points_scale = blocking_point_scale
		v.opportunity_cost_scale = opportunity_cost_scale

	if verbose:
		print_list = sorted(list(cards_points.items()), key=lambda pair: pair[1].total, reverse=True)

		print('Possible picks:')
		for card, points in print_list:
			print(f'\t{str(card) + ":":24s} {points}')

	if always_take_chopsticks and Card.Chopsticks in hand:
		if verbose:
			print('"Always take chopsticks" is set, so removing non chopstick choices')
		cards_points = {
			card: points for card, points in cards_points.items()
			if (isinstance(card, Card) and card == Card.Chopsticks) or (isinstance(card, Tuple) and Card.Chopsticks in card)
		}
		assert cards_points

	# Take highest point value option (if tied, take random from tied)

	max_points = max([v.total for v in cards_points.values()])
	max_point_picks = [
		card
		for card, points
		in cards_points.items()
		if points.total >= (max_points - FLOAT_EPSILON)
	]

	if verbose:
		if len(max_point_picks) > 1:
			print(f'Picking randomly from top: [{card_names(max_point_picks)}]')
		else:
			print(f'Picking highest: {max_point_picks[0]}')

	return random.choice(max_point_picks)
