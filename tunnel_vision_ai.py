#!/usr/bin/env python

from collections.abc import Collection, Sequence
from typing import Optional, Tuple, Union

from ai import AI
from player import PlayerState
from cards import Card, card_names
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


def _sashimi_avg_pts(
		num_cards_in_hand: int,
		plate: Optional[Sequence[Card]],
		num_chopsticks: Optional[int],
		) -> int:
	assert num_cards_in_hand > 0

	if plate is None:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# TODO: factor in num_cards_in_hand?
		return 3

	num_sashimi_needed = get_num_sashimi_needed(plate)

	num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	if num_sashimi_needed > num_cards_in_hand:
		return 0

	if num_sashimi_needed == 1:
		# If this one completes a set, then this is straight-up 10 points, no further calculations needed
		return 10

	elif num_sashimi_needed == 2:
		# What are the odds we will see 1 more after this one?
		# 14/108 cards are Sashimi = 13%, and we've already seen 2 = 12/106

		# 8-card game, turn 2: 2.38
		avg_num_sashimi_yet_to_see = num_cards_yet_to_see * 12/106

		# Right now (before we've sunk the cost), this one card is only worth half the 10 points
		# 8-card game, turn 2: 5 points
		return (10/2) * min(1.0, avg_num_sashimi_yet_to_see)

	elif num_sashimi_needed == 3:
		# What are the odds we will see 2 more? (on 2 separate hands, unless num_chopsticks)
		
		# 8-card game, turn 1: 3.4
		# 8-card game, turn 2: 2.55
		avg_num_sashimi_yet_to_see = num_cards_yet_to_see * 13/107

		# The number of cards we'll actually see is some sort of distribution with a mean of that number,
		# but the actual distribution is going to have skew
		# Very very very rough approximation, just divide by 2 and that's the odds that we'll see 2
		if num_chopsticks:
			odds_seeing_2_sashimi = 0.5 * avg_num_sashimi_yet_to_see
		else:
			# Even rougher approximation, subtract 0.1 to adjust for odds they could both be on same turn
			odds_seeing_2_sashimi = 0.4 * avg_num_sashimi_yet_to_see

		# Scale by 90% to adjust for probability we would actually take the 2nd sashimi (3rd is considered a sure thing)

		# 8-card game, turns 1-2: 3 points (regardless of chopsticks)
		return (10/3) * min(1.0, odds_seeing_2_sashimi) * 0.9


def _tempura_avg_pts(
		num_cards_in_hand: int,
		plate: Optional[Sequence[Card]],
		) -> int:
	assert num_cards_in_hand > 0

	if plate is None:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# TODO: factor in num_cards_in_hand?
		return 2

	num_tempura_needed = get_num_tempura_needed(plate)
	num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	if num_tempura_needed > num_cards_in_hand:
		return 0

	if num_tempura_needed == 1:
		return 5

	elif num_tempura_needed == 2:
		# 8-card game, turn 1: 3.4
		avg_num_tempura_yet_to_see = num_cards_yet_to_see * 13/107
		return (5/2) * min(1.0, avg_num_tempura_yet_to_see)


def _wasabi_avg_points(num_cards_in_hand: int, num_unused_wasabi: Optional[int]) -> Union[int, float]:

	if num_unused_wasabi is None:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# There's a chance another player could have unused wasabi, hence 2.1 instead of 2
		return min((num_cards_in_hand - 1) / 2.1, 6)

	# 8-card game, turn 1: worth 3.5 points
	# 8-card game, turn 2: worth 3 points, or 1.5 if we already have wasabi
	return min((num_cards_in_hand - 1) / (2 ** (1 + num_unused_wasabi)), 6)


def _nigiri_opportunity_cost(card: Card, num_unused_wasabi: Optional[int], num_cards_on_plate: int, num_cards_in_hand: int) -> Union[int, float]:

	# If this is a squid, then we can't possibly do better; no opportunity cost
	if card not in [Card.EggNigiri, Card.SalmonNigiri]:
		return 0.0

	if num_unused_wasabi is None:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		# TODO: what to count for this?
		return 0

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


def _nigiri_avg_points(card: Card, num_unused_wasabi: Optional[int], num_cards_on_plate: int, num_cards_in_hand: int) -> Union[float, int]:

	opportunity_cost = _nigiri_opportunity_cost(
		card,
		num_unused_wasabi,
		num_cards_on_plate=num_cards_on_plate,
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
		return 3*wasabi_scale - opportunity_cost

	if card == Card.SalmonNigiri:
		return 2*wasabi_scale - opportunity_cost

	if card == Card.EggNigiri:
		return wasabi_scale - opportunity_cost

	raise KeyError(repr(card))


def _maki_avg_points(card: Card, num_players: int) -> float:
	if card == Card.Maki3:
		return 4.5 / num_players
	
	if card == Card.Maki2:
		return 3.0 / num_players
	
	if card == Card.Maki1:
		return 1.5 / num_players
	
	raise KeyError(repr(card))


def _dumpling_avg_pts(num_cards_in_hand: int, plate: Optional[Sequence[Card]]) -> int:

	if plate is None:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		return 2

	n_dumpling = count_card(plate, Card.Dumpling)

	# If already 5 dumplings, there's no point taking any more
	if n_dumpling >= 5:
		return 0

	points_this_dumpling = n_dumpling + 1

	# TODO: of course we could look at other plates/hands to determine the odds more accurately than this
	# That's not the point of this particular basic AI though

	# Taking a dumpling now also makes future dumplings more valuable
	# How many more dumplings are we expected to see?
	num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2
	# 14/108 cards are Dumplings = 13%
	# 8-card hand, turn 1: 3.4
	avg_num_dumplings_yet_to_see = num_cards_yet_to_see * 13/107

	# Of course, these potential points are only valid if we actually take the dumplings
	# How many of these are we likely to actually take?
	# As a very rough guess, assume we'll take half
	avg_num_dumplings_yet_to_take = 0.5*avg_num_dumplings_yet_to_see

	# This makes them each more valuable by 1 point
	avg_points_future_dumplings = avg_num_dumplings_yet_to_take

	# 8-card game, turn 1: 1 + 1.7 = 2.7
	return points_this_dumpling + avg_points_future_dumplings


def _pudding_avg_pts(num_players: int) -> float:
	if num_players > 2:
		# 12 points total, across 3 rounds
		# 5-player: 0.8 points
		# 4-player: 1 point
		# 3-player: 1.33 points
		return 4 / num_players
	else:
		# In 2-player, there's no -6, so 6 points total; worth 1 point
		return 2 / num_players


def _chopsticks_avg_points(num_chopsticks: Optional[int], num_cards_on_plate: int, num_cards_in_hand: int) -> Union[int, float]:

	if num_chopsticks is None:
		# General case - on average, how many points is this worth for an arbitrary player we know nothing else about?
		num_remaining_turns_could_use_these_chopsticks = max(num_cards_in_hand - 2 - 1, 0)
		return 0.5 * num_remaining_turns_could_use_these_chopsticks

	assert num_chopsticks >= 0

	# If there are 3 cards in hand and 0 chopsticks on plate, there's 1 more turn we could use them
	num_remaining_turns_could_use_these_chopsticks = num_cards_in_hand - 2 - num_chopsticks

	if num_remaining_turns_could_use_these_chopsticks <= 0:
		return 0

	# num_cards_yet_to_see = num_cards_in_hand * (num_cards_in_hand - 1) // 2

	# Guesstimate about 0.5 point per turn left? (Even worse if we already have chopsticks)
	# TODO: maybe a bit higher than this in early turns (before people have taken all the good stuff)
	points = (0.5 ** (num_chopsticks + 1)) * num_remaining_turns_could_use_these_chopsticks

	# 8-card game, turn 1: 3 points

	return points


def _using_chopsticks_opportunity_cost(num_chopsticks: int, num_cards_on_plate: int, num_cards_in_hand: int) -> Union[int, float]:

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


def _avg_points_not_counting_blocking(
		card: Card,
		plate: Optional[Sequence[Card]],
		num_cards: int,
		num_players: int,
		num_unused_wasabi: Optional[int],
		num_chopsticks: Optional[int],
		num_cards_on_plate: Optional[int] = None,
		) -> Union[int, float]:

	if num_cards_on_plate is None:
		if plate is None:
			raise ValueError('Must provide either plate or num_cards_on_plate')
		num_cards_on_plate = len(plate)
	elif (plate is not None) and (num_cards_on_plate != len(plate)):
		raise ValueError('Conflictng num_cards_on_plate')

	if card == Card.Sashimi:
		return _sashimi_avg_pts(num_cards_in_hand=num_cards, plate=plate, num_chopsticks=num_chopsticks)

	if card == Card.Tempura:
		return _tempura_avg_pts(num_cards_in_hand=num_cards, plate=plate)

	if card == Card.Dumpling:
		return _dumpling_avg_pts(num_cards_in_hand=num_cards, plate=plate)

	if card == Card.Wasabi:
		return _wasabi_avg_points(num_cards_in_hand=num_cards, num_unused_wasabi=num_unused_wasabi)

	if card.is_nigiri():
		return _nigiri_avg_points(card, num_unused_wasabi=num_unused_wasabi, num_cards_on_plate=num_cards_on_plate, num_cards_in_hand=num_cards)

	if card.is_maki():
		return _maki_avg_points(card, num_players=num_players)

	if card == Card.Pudding:
		return _pudding_avg_pts(num_players=num_players)
	
	if card == Card.Chopsticks:
		return _chopsticks_avg_points(num_chopsticks=num_chopsticks, num_cards_on_plate=num_cards_on_plate, num_cards_in_hand=num_cards)

	raise KeyError(repr(card))


def _avg_points(
		card: Card,
		plate: Sequence[Card],
		num_cards: int,
		num_players: int,
		num_unused_wasabi: int,
		num_chopsticks: int,
		blocking_point_scale: float,
		) -> float:

	avg_points_me = _avg_points_not_counting_blocking(
		card=card,
		plate=plate,
		num_cards=num_cards,
		num_players=num_players,
		num_unused_wasabi=num_unused_wasabi,
		num_chopsticks=num_chopsticks,
	)

	avg_relative_points_from_blocking = _avg_points_not_counting_blocking(
		card=card,
		plate=None,
		num_cards=num_cards,
		num_players=num_players,
		num_unused_wasabi=None,
		num_chopsticks=None,
		num_cards_on_plate=len(plate),
	) / (num_players - 1)

	return avg_points_me + blocking_point_scale * avg_relative_points_from_blocking


def _pair_avg_points(
		cards: Tuple[Card, Card],
		plate: Sequence[Card],
		num_cards: int,
		num_players: int,
		num_unused_wasabi: int,
		num_chopsticks: int,
		blocking_point_scale: float,
		) -> Union[int, float]:

	assert num_cards >= 2
	assert num_chopsticks >= 1

	card1, card2 = cards
	num_chopsticks -= 1

	card1_points = _avg_points(
		card1,
		plate=plate,
		num_cards=num_cards,
		num_players=num_players,
		num_unused_wasabi=num_unused_wasabi,
		num_chopsticks=num_chopsticks,
		blocking_point_scale=blocking_point_scale,
	)

	plate_after = list(plate) + [card1]

	if card1 == Card.Wasabi:
		num_unused_wasabi += 1
	
	if card1 == Card.Chopsticks:
		num_chopsticks += 1

	card2_points = _avg_points(
		card2,
		plate=plate_after,
		num_cards=(num_cards - 1),
		num_players=num_players,
		num_unused_wasabi=num_unused_wasabi,
		num_chopsticks=num_chopsticks,
		blocking_point_scale=blocking_point_scale,
	)

	return card1_points + card2_points


"""
Simple AI that just tries to maximize points in the moment
Only looks at what's on current plate and how many cards are left
Doesn't look at other players' hands/plates, or what other cards are still out there
Minimal regard for opportunity cost of future moves
"""
class TunnelVisionAi(AI):
	def __init__(self, blocking_point_scale: float = DEFAULT_BLOCKING_POINT_SCALE):
		self.blocking_point_scale = blocking_point_scale

	def play_turn(self, player_state: PlayerState, hand: Collection[Card], verbose=False) -> Union[Card, Tuple[Card, Card]]:
		n_cards = len(hand)
		assert n_cards > 0

		if n_cards == 1:
			return hand[0]

		plate = player_state.plate
		num_players = player_state.get_num_players()

		num_chopsticks = count_card(plate, Card.Chopsticks)
		num_unused_wasabi = get_num_unused_wasabi(plate)

		can_use_chopsticks = num_chopsticks and len(hand) > 1

		# TODO: could make this slightly more efficient by eliminating some obvious picks (don't take lower nigiri or Maki)
		cards_points = {
			card: float(_avg_points(
				card,
				plate=plate,
				num_cards=len(hand),
				num_players=num_players,
				num_unused_wasabi=num_unused_wasabi,
				num_chopsticks=num_chopsticks,
				blocking_point_scale=self.blocking_point_scale,
			)) for card in set(hand)
		}

		if can_use_chopsticks:
			chopstick_opportunity_cost = _using_chopsticks_opportunity_cost(
				num_chopsticks=num_chopsticks,
				num_cards_on_plate=len(plate),
				num_cards_in_hand=n_cards,
			)

			chopstick_pairs = meaningful_chopstick_pairs(hand=hand, num_unused_wasabi=num_unused_wasabi)
			for chopstick_pair in chopstick_pairs:
				cards_points[chopstick_pair] = float(
					_pair_avg_points(
						chopstick_pair,
						plate=plate,
						num_cards=len(hand),
						num_players=num_players,
						num_unused_wasabi=num_unused_wasabi,
						num_chopsticks=num_chopsticks,
						blocking_point_scale=self.blocking_point_scale,
				)) - chopstick_opportunity_cost

		# Take highest point value option (if tied, take random from tied)

		max_points = max(cards_points.values())
		max_point_picks = [
			card
			for card, points
			in cards_points.items()
			if points >= (max_points - FLOAT_EPSILON)
		]

		if verbose:
			print_list = sorted(list(cards_points.items()), key=lambda pair: pair[1], reverse=True)
			print_list = ["%s: %.2f" % card for card in print_list]
			print_list = ", ".join(print_list)

			if len(max_point_picks) > 1:
				print('Point values: {%s}, picking randomly from top: [%s]' % (print_list, card_names(max_point_picks)))
			else:
				print('Point values: {%s}, picking highest: %s' % (print_list, max_point_picks[0]))

		return random.choice(max_point_picks)
