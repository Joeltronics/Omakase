#!/usr/bin/env python

from collections.abc import Sequence
from typing import Tuple, List, Iterable, Optional


DEFAULT_ELO = 1500
MIN_ELO = 100
MIN_K = 2
MAX_K = 32


def k_factor(num_games: int) -> float:
	k = 800 / max(num_games, 1)
	k = min(k, float(MAX_K))
	k = max(k, float(MIN_K))
	return k


def elo(
		scores: Tuple[float, float],
		prev_ratings: Tuple[Optional[float], Optional[float]] = (None, None),
		k=16.0,
		delta=False,
		) -> Tuple[float, float]:
	"""
	Standard (2-player) Elo rating algorithm
	:param scores: Player scores (0 points for loss, 0.5 for draw, 1 for win)
	:param ratings: Previous Elo ratings
	:param k: Elo K-factor
	:param delta: return change in score instead of new score

	:returns: (new rating A, new rating B), or (delta A, delta B) if delta
	"""

	ra, rb = prev_ratings
	sa, sb = scores

	if ra is None:
		ra = DEFAULT_ELO
	if rb is None:
		rb = DEFAULT_ELO

	qa = 10.0 ** (ra / 400.0)
	qb = 10.0 ** (rb / 400.0)

	ea = qa / (qa + qb)
	eb = qb / (qa + qb)

	da = k * (sa - ea)
	db = k * (sb - eb)

	if delta:
		return (da, db)

	sa = max(sa + da, MIN_ELO)
	sb = max(sb + db, MIN_ELO)

	return sa, sb


def multiplayer_elo(
		ranks: Sequence[int],
		ratings: Sequence[Sequence],
		num_prev_games: int,
		) -> List[float]:
	"""
	:param players: [(Previous rating, rank), ...]
	:returns: [New rating, ...]
	"""

	"""
	TODO: try this instead - same idea but only compare against players immediately above or below:
	http://www.tckerrigan.com/Misc/Multiplayer_Elo/
	"""

	if len(ranks) != len(ratings):
		raise ValueError('len(ranks) != len(ratings)')
	num_players = len(ranks)

	new_ratings = []

	# Each game is actually (n-1) Elo "games"
	# TODO: this assumes the number of players was the same in every game
	k = k_factor(num_games=((num_players - 1) * (1 + num_prev_games)))

	for player_idx, (player_rank, player_rating) in enumerate(zip(ranks, ratings)):

		delta = 0

		for opponent_idx, (opponent_rank, opponent_rating) in enumerate(zip(ranks, ratings)):
			if opponent_idx == player_idx:
				continue

			prev_ratings = (player_rating, opponent_rating)

			if player_rank > opponent_rank:
				# Higher rank = player lost to opponent
				scores = (0.0, 1.0)
			elif player_rank < opponent_rank:
				# Lower rank = player beat opponent
				scores = (1.0, 0.0)
			else:
				# Draw
				scores = (0.5, 0.5)

			delta += elo(scores=scores, prev_ratings=prev_ratings, k=k, delta=True)[0]

		player_new_rating = max(player_rating + delta, float(MIN_ELO))
		new_ratings.append(player_new_rating)

	assert len(new_ratings) == num_players
	return new_ratings
