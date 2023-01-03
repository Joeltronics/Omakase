#!/usr/bin/env python

import argparse
from collections.abc import Sequence
from copy import copy
from dataclasses import dataclass, field
import itertools
from multiprocessing import Pool
import random
from typing import List, Optional

from tqdm import tqdm, trange

from random_ai import RandomAI, RandomPlusAI, RandomPlusPlusAI
from recursive_solver_ai import RecursiveSolverAI, LaterRecursiveAi
from present_value_based_ai import TunnelVisionAI

from cards import Card
from deck import Deck, get_deck_distribution
from elo import multiplayer_elo, DEFAULT_ELO
from game import Game
from player import get_player_name
from utils import add_numbers_to_duplicate_names, random_order_and_inverse


def _bool_arg(val) -> bool:
	return bool(int(val))


@dataclass
class PlayerGameStats:
	name: str
	total_num_points: int = 0
	margin_from_winner: int = 0
	ranks: List[int] = field(default_factory=list)
	elo: float = DEFAULT_ELO
	elo_history: Optional[List[int]] = None


def play_game(*, num_players, players, player_names, verbose, randomize_player_order=False, random_seed=None, **game_kwargs):

	random.seed(random_seed)

	inverse_player_order = None
	if randomize_player_order:
		player_order, inverse_player_order = random_order_and_inverse(num_players)
		player_names = [player_names[idx] for idx in player_order]
		players = [players[idx] for idx in player_order]

		if verbose:
			print('Randomized player order:')
			for idx, name in enumerate(player_names):
				print(f'\t{idx + 1}: {name}')
			print()

	# TODO: once there are stateful AI, will need to create new ones each game
	game = Game(
		player_names=player_names,
		players=players,
		num_players=num_players,
		verbose=verbose,
		**game_kwargs)
	result = game.play()

	if inverse_player_order is not None:
		result = [result[idx] for idx in inverse_player_order]

	return result


def _play_game_from_kwargs(kwargs, /):
	"""
	Wrapper for play_game, for multiprocessing.Pool.imap purposes
	"""
	return play_game(**kwargs)


def _get_deck_distribution(args):
	deck_dist = get_deck_distribution()

	if not args.pudding:
		deck_dist[Card.Pudding] = 0

	if not args.chopsticks:
		deck_dist[Card.Chopsticks] = 0

	return deck_dist


def _setup_players(args):
	if args.recursive_test:
		print('--recursive-test given, using recursive AI')

		if args.omniscient:
			players = [RecursiveSolverAI(), TunnelVisionAI()]
		else:
			players = [LaterRecursiveAi(non_recursive_ai=TunnelVisionAI()), TunnelVisionAI()]

		if args.players >= 3:
			players.append(RandomPlusPlusAI())
		if args.players >= 4:
			players.append(RandomPlusAI())
		num_random_ai = max(0, args.players - len(players))
		players.extend([RandomAI() for _ in range(num_random_ai)])
	else:
		players = [TunnelVisionAI(), RandomPlusPlusAI()]
		if args.players >= 3:
			players.append(RandomPlusAI())

	num_random_ai = max(0, args.players - len(players))
	players.extend([RandomAI() for _ in range(num_random_ai)])

	player_names = add_numbers_to_duplicate_names([player.get_name() for player in players])

	return players, player_names


def _process_results(
		game_results,
		player_names: Sequence[str],
		include_elo_history: bool,
		) -> list[PlayerGameStats]:

	num_players = len(player_names)

	player_game_stats = [PlayerGameStats(name=name) for name in player_names]
	if include_elo_history:
		for stats in player_game_stats:
			stats.elo_history = []

	for game_idx, result in enumerate(tqdm(game_results, desc='Processing results')):
		if len(result) != num_players:
			raise ValueError(f'Game did not return expected length of results ({len(result)} != {num_players})')

		winning_score = max(r.score for r in result)

		new_elos = multiplayer_elo(
			ranks=[r.rank for r in result],
			ratings=[p.elo for p in player_game_stats],
			num_prev_games=game_idx)

		for idx, (result, new_elo) in enumerate(zip(result, new_elos)):
			margin = result.score - winning_score
			player_game_stats[idx].total_num_points += result.score
			player_game_stats[idx].ranks.append(result.rank)
			player_game_stats[idx].margin_from_winner += margin
			player_game_stats[idx].elo = new_elo
			if player_game_stats[idx].elo_history is not None:
				player_game_stats[idx].elo_history.append(new_elo)

	return player_game_stats


def _print_results(player_game_stats: Sequence[PlayerGameStats], num_games: int) -> None:
	print()
	print(f'Results from {num_games} games')
	print()
	# TODO: dynamic table column widths, in case of long player name or player with >= 10,000 wins
	print(f'{"Player":<20} | {"Wins":^10} | Avg rank | Avg score | Avg margin | Elo')
	print(f'{"-"*20} | {"-"*10} | {"-"*8} | {"-"*9} | {"-"*10} | {"-"*4}')
	for player in player_game_stats:
		num_wins = sum(rank == 1 for rank in player.ranks)
		pct_wins = num_wins / num_games * 100.0
		avg_rank = sum(player.ranks) / num_games
		avg_score = player.total_num_points / num_games
		avg_margin = player.margin_from_winner / num_games
		print(f'{player.name:<20} |{num_wins:>5} ={pct_wins:3.0f}% | {avg_rank:>8.2f} | {avg_score:>9.2f} | {avg_margin:>10.2f} | {player.elo:>4.0f}')


def _plot_elo(plt, player_game_stats: Sequence[PlayerGameStats]) -> None:
	assert plt is not None
	print()
	print('Plotting Elo ratings')

	fig, ax = plt.subplots(1, 1)
	fig.suptitle('Elo rating convergence')

	for player in player_game_stats:
		assert player.elo_history is not None
		ax.plot(player.elo_history, label=player.name)

	ax.grid()
	ax.legend()
	ax.set_xlabel('Game number')
	ax.set_ylabel('Elo rating')
	print('Showing plots')
	plt.show()


def parse_args() -> argparse.Namespace:

	parser = argparse.ArgumentParser()

	g = parser.add_argument_group('Basic game parameters')
	g.add_argument('-p', '--players', default=4, type=int, help='Number of players')
	g.add_argument('--seed', type=int, help='Deterministic random seed (currently only works for single-threaded)')
	g.add_argument('--short', action='store_true', help='Play very short game (1 round of 3 cards)')

	g = parser.add_argument_group('Alternate game rules')
	g.add_argument('--pudding',    metavar='0/1', default=True,  type=_bool_arg, help='Use pudding - Default 1')
	g.add_argument('--chopsticks', metavar='0/1', default=True, type=_bool_arg, help='Use chopsticks - Default 1')
	g.add_argument('--omniscient', metavar='0/1', default=None,  type=_bool_arg, help='Omniscient mode (all players see all cards) - Default 0, or 1 if --short')

	g = parser.add_argument_group('Repeated games')
	g.add_argument('-n', '--num-games', default=1, type=int, help='Number of games to play (default 1)')
	g.add_argument('--randomize-order', metavar='0/1', default=None, type=_bool_arg, help='Randomize player order - Default 1 if multiple games, 0 if not')
	g.add_argument('--single-thread', action='store_true', help='Force single-threaded')
	g.add_argument('--plot-elo', action='store_true', help='Plot Elo convergence')

	g = parser.add_argument_group('Debugging')
	g.add_argument('--pause', dest='pause_after_turn', action='store_true', help='Pause for user input after each round')
	g.add_argument('--recursive-test', action='store_true', help='Test recursive solver')

	args = parser.parse_args()

	args.num_rounds = None
	args.num_cards_per_player = None

	# --short

	if args.short:
		print('--short given, playing short game')
		args.num_rounds = 1
		args.num_cards_per_player = 3

	# Handle a few more default arg values

	if args.randomize_order is None:
		args.randomize_order = args.num_games > 1

	if args.omniscient is None:
		args.omniscient = args.short

	if args.num_rounds is None:
		args.num_rounds = 3

	return args


def main():
	args = parse_args()

	plt = None
	if args.plot_elo:
		from matplotlib import pyplot as plt

	players, player_names = _setup_players(args)
	print(f'{args.players} Players: ' + ', '.join(player_names))

	deck_dist = _get_deck_distribution(args)

	play_game_kwargs = dict(
		num_players=args.players,
		deck_dist=deck_dist,
		omniscient=args.omniscient,
		player_names=player_names,
		players=players,
		verbose=(args.num_games == 1),
		randomize_player_order=args.randomize_order,
		pause_after_turn=args.pause_after_turn,
		num_cards_per_player=args.num_cards_per_player,
		num_rounds=args.num_rounds,
	)

	if args.num_games == 1:
		play_game(random_seed=args.seed, **play_game_kwargs)
		return

	use_multiprocessing = (not args.single_thread) and (args.num_games > 10) and (not args.pause_after_turn) and (args.seed is None)

	# TODO: support random seed with multiprocessing
	if not use_multiprocessing:
		if args.seed is None:
			random.seed()
			args.seed = random.randint(0, (2 ** 32) - 1 - args.num_games)
			print(f'Random seed: {args.seed}')
		else:
			print(f'Using provided random seed: {args.seed}')

	if use_multiprocessing:
		with Pool() as p:
			game_results = list(
				tqdm(
					p.imap(_play_game_from_kwargs, itertools.repeat(play_game_kwargs, args.num_games)),
					total=args.num_games,
					desc=f'Playing {args.num_games} games (multithreaded)',
				)
			)
	else:
		game_results = [
			play_game(random_seed=(args.seed + game_idx), **play_game_kwargs)
			for game_idx in trange(args.num_games, desc=f'Playing {args.num_games} games')
		]

	player_game_stats = _process_results(game_results=game_results, player_names=player_names, include_elo_history=args.plot_elo)

	_print_results(player_game_stats=player_game_stats, num_games=args.num_games)

	if args.plot_elo:
		_plot_elo(plt, player_game_stats)


if __name__ == "__main__":
	main()


"""
Card distribution:
	14x Tempura
	14x Sashimi
	14x Dumpling
	12x 2-Maki
	8x 3-Maki
	6x 1-Maki
	10x Salmon Nigiri
	5x Squid Nigiri
	5x Egg Nigiri
	10x Pudding
	6x Wasabi
	4x Chopsticks

Card scoring:
	Maki: most 6, second 3
	Tempura: 2x -> 5 points
	Sashimi: 3x -> 10 points
	Dumplings: 1/2/3/4/5 gets 1/3/6/10/15
	Nigiri: Squid 3, Salmon 2, Egg 1
	Wasabi: 3x next Nigiri
	Chopsticks: swap later
	Puddings: Most 6, Least -6

Scoring specifics:
	If tied, always round down
	If tied 1st place Maki, split the 6, no 2nd place awarded
	If tied 2nd place Maki, split the 3
	In 2-player, nobody loses points for pudding

Starting hand per player:
	2: 10
	3: 9
	4: 8
	5: 7

Total percentage of deck used (108 cards total):
	2: 2*10*3 = 60 / 108 = 56%
	3: 3*9*3 =  81 / 108 = 75%
	4: 4*8*3 =  96 / 108 = 89%
	5: 5*7*3 = 105 / 108 = 97%
"""
