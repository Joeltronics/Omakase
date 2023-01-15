#!/usr/bin/env python

import argparse
from collections.abc import Sequence
import colorama
from copy import copy
from dataclasses import dataclass, field
import itertools
from multiprocessing import Pool
import random
from typing import List, Optional

from tqdm import tqdm, trange

from random_ai import RandomAI, RandomPlusAI, RandomPlusPlusAI
from recursive_solver_ai import RecursiveSolverAI, LaterRecursiveAI
from present_value_based_ai import HandOnlyAI, TunnelVisionAI, BasicPresentValueAI

from cards import Card
from deck import Deck, get_deck_distribution
from elo import multiplayer_elo, DEFAULT_ELO
from game import Game, PlayerResult
from player import get_player_name
from utils import add_numbers_to_duplicate_names, ceil_divide, right_pad


RESET_ALL = colorama.Style.RESET_ALL


def _bool_arg(val) -> bool:
	return bool(int(val))



@dataclass
class PlayerMatchup:
	num_games: int = 0
	num_wins: int = 0
	num_ties: int = 0

	# Average rank in games including this player
	# One case this can be useful (vs simple win rate) is cases where one AI has a strategy that generally
	# works well but is vulnerable to blocking, and another AI is likely to block (but does much worse on average)
	sum_rank: float = 0.0

	@property
	def num_losses(self) -> int:
		return self.num_games - self.num_wins - self.num_ties

	@property
	def win_rate(self) -> Optional[float]:
		return (self.num_wins + 0.5*self.num_ties) / self.num_games if self.num_games else None

	@property
	def avg_rank(self) -> Optional[float]:
		return self.sum_rank / self.num_games if self.num_games else None


@dataclass
class PlayerGameStats:
	name: str
	total_num_points: int = 0
	margin_from_winner: int = 0
	ranks: list[int] = field(default_factory=list)
	normalized_ranks: Optional[list[int]] = field(default_factory=list)

	elo: float = DEFAULT_ELO
	num_elo_matchups_played = 0
	elo_history: Optional[list[int]] = None

	matchups: dict[str, PlayerMatchup] = field(default_factory=dict)


def play_game(*,
		num_players: int,
		players,
		player_names,
		verbose,
		randomize_player_order=False,
		random_seed=None,
		**game_kwargs,
		) -> list[PlayerResult]:

	random.seed(random_seed)

	assert (num_players == 0) or (2 <= num_players <= len(players))
	if not num_players:
		num_players = random.randint(2, min(5, len(players)))

	idxs = list(range(len(players)))
	if num_players < len(players):
		# Randomly select players (and order) to play this game
		idxs = random.sample(idxs, num_players)
		if not randomize_player_order:
			idxs.sort()

	elif randomize_player_order:
		random.shuffle(idxs)

	assert len(idxs) == num_players
	assert len(set(idxs)) == num_players, f"Not all idxs are unique: {idxs}"

	players = [players[idx] for idx in idxs]
	player_names = [player_names[idx] for idx in idxs]

	assert len(players) == num_players
	assert len(player_names) == num_players

	if verbose:
		print('Players:')
		for idx, name in enumerate(player_names):
			print(f'\t{idx + 1}: {name}')
		print()

	# TODO: once there are stateful AI, will need to create new ones each game
	game = Game(
		player_names=player_names,
		players=players,
		verbose=verbose,
		**game_kwargs)
	result = game.play()

	return result


def _play_game_from_kwargs(kwargs, /) -> list[PlayerResult]:
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

	# TODO: if randomizing player count (args.num_players == 0), include duplicates of same AI

	ai_class_constructors = []

	if args.recursive_test:
		print('--recursive-test given, using recursive AI')
		if args.omniscient:
			ai_class_constructors.append(lambda: RecursiveSolverAI(consolidation_type='average'))
		else:
			ai_class_constructors.append(lambda: LaterRecursiveAI(non_recursive_ai=BasicPresentValueAI(), consolidation_type='average'))

	ai_class_constructors += [
		BasicPresentValueAI,
		TunnelVisionAI,
		RandomPlusPlusAI,
		RandomPlusAI,
		HandOnlyAI,
		lambda: RandomAI(weight_by_unique_cards=False),
		lambda: RandomAI(weight_by_unique_cards=True),
	]

	if args.recursive_test:
		# Put these at the end, so e.g. if we're only running 1 game we don't end up with almost entirely recursive AI
		if args.omniscient:
			ai_class_constructors.append(lambda: RecursiveSolverAI(consolidation_type='worst'))
			ai_class_constructors.append(lambda: RecursiveSolverAI(consolidation_type='best'))
		else:
			ai_class_constructors.append(lambda: LaterRecursiveAI(non_recursive_ai=BasicPresentValueAI(), consolidation_type='worst'))
			ai_class_constructors.append(lambda: LaterRecursiveAI(non_recursive_ai=BasicPresentValueAI(), consolidation_type='best'))

	players = []
	for constructor in ai_class_constructors:
		if args.num_players and len(players) >= args.num_players:
			break
		players.append(constructor())

	# Pad with as many random AI as it takes to hit minimum number of players
	# (in practice, won't actually hit this unless commenting out AIs or doing something else weird)
	pad_to_num_players = args.num_players or 5
	num_random_ai = max(0, pad_to_num_players - len(players))
	players.extend([RandomAI() for _ in range(num_random_ai)])

	if args.num_players:
		assert len(players) == args.num_players

	player_names = add_numbers_to_duplicate_names([player.get_name() for player in players])
	assert len(player_names) == len(players)

	return players, player_names


def _process_results(
		game_results: Sequence[Sequence[PlayerResult]],
		player_names: Sequence[str],
		include_elo_history: bool,
		) -> list[PlayerGameStats]:

	different_player_counts = len({len(result) for result in game_results}) > 1

	# TODO: separate stats (at least Elo) per player count, in case one AI does better at a certain player count

	# TODO: If there are multiple of the same AI, consolidate their stats

	# TODO: should be able to calculate Elo all at once based on overall matchup stats instead of game-by-game

	player_game_stats_dict = {
		name: PlayerGameStats(name=name, normalized_ranks=([] if different_player_counts else None), elo_history=([] if include_elo_history else None))
		for name in player_names
	}

	for game_result in tqdm(game_results, desc='Processing results'):

		num_players_this_game = len(game_result)
		player_names_this_game = [r.name for r in game_result]

		winning_score = max(r.score for r in game_result)

		new_elos = multiplayer_elo(
			ranks=[r.rank for r in game_result],
			ratings=[player_game_stats_dict[name].elo for name in player_names_this_game],
			num_prev_matchups=[player_game_stats_dict[name].num_elo_matchups_played for name in player_names_this_game],
		)

		for player_game_result, new_elo in zip(game_result, new_elos):
			player_stats = player_game_stats_dict[player_game_result.name]
			margin = player_game_result.score - winning_score
			player_stats.total_num_points += player_game_result.score
			player_stats.margin_from_winner += margin

			my_rank = player_game_result.rank

			assert 1 <= my_rank <= num_players_this_game
			player_stats.ranks.append(my_rank)
			if player_stats.normalized_ranks is None:
				normalized_rank = None
			else:
				# Ranks will be in range [1, N], convert to range [0, 1]
				normalized_rank = (my_rank - 1) / (num_players_this_game - 1)
				assert 0 <= normalized_rank <= 1
				player_stats.normalized_ranks.append(normalized_rank)

			player_stats.elo = new_elo
			player_stats.num_elo_matchups_played += num_players_this_game - 1
			if player_stats.elo_history is not None:
				player_stats.elo_history.append(new_elo)

			for other_player_result in game_result:
				if other_player_result == player_game_result:
					continue

				if other_player_result.name not in player_stats.matchups:
					player_stats.matchups[other_player_result.name] = PlayerMatchup()

				matchup = player_stats.matchups[other_player_result.name]

				other_rank = other_player_result.rank
				matchup.num_games += 1
				if my_rank < other_rank:
					matchup.num_wins += 1
				elif my_rank == other_rank:
					matchup.num_ties += 1

				matchup.sum_rank += normalized_rank if (normalized_rank is not None) else my_rank

	return list(player_game_stats_dict.values())


def _print_results(player_game_stats: Sequence[PlayerGameStats], num_games: int, print_full_matchups=False) -> None:

	assert all(bool(p.normalized_ranks) == bool(player_game_stats[0].normalized_ranks) for p in player_game_stats[1:])

	player_game_stats = sorted(player_game_stats, key = lambda pgs: pgs.elo, reverse=True)
	num_players = len(player_game_stats)

	name_len = max(len(player.name) for player in player_game_stats)

	print()
	print(f'Results from {num_games} games')

	print()
	print('Summary:')
	print()

	print(f'{right_pad("Player", name_len)} | {"Wins":^10} | Avg rank | Avg score | Avg margin | Elo')
	print(f'{"-"*name_len} | {"-"*10} | {"-"*8} | {"-"*9} | {"-"*10} | {"-"*4}')
	for player in player_game_stats:
		player_num_games = len(player.ranks)
		num_wins = sum(rank == 1 for rank in player.ranks)
		pct_wins = num_wins / player_num_games * 100.0
		avg_rank = sum(player.normalized_ranks if player.normalized_ranks else player.ranks) / player_num_games
		avg_score = player.total_num_points / player_num_games
		avg_margin = player.margin_from_winner / player_num_games
		print(f'{right_pad(player.name, name_len)} |{num_wins:>5} ={pct_wins:3.0f}% | {avg_rank:>8.2f} | {avg_score:>9.2f} | {avg_margin:>10.2f} | {player.elo:>4.0f}')

	print()
	print('Matchups:')
	print()

	def _short_player_name(name: str) -> str:
		name = name.replace('AI', '').replace('Ai', '').replace('Bot', '').replace('BOT', '')
		name = ''.join([c for c in name if c.isalnum() and not c.islower()])
		return f'{name:^5}'

	print(f'{right_pad("Player", name_len)} | ' + ' | '.join(_short_player_name(p.name) for p in player_game_stats) + ' |')
	separator = f'{"-"*name_len} | ' + ' | '.join(['-'*5 for _ in range(num_players)]) + ' |'
	print(separator)
	for player in player_game_stats:

		matchups = [
			(player.matchups[p.name] if p != player else None)
			for p in player_game_stats
		]

		win_rates = [(m.win_rate if m is not None else None) for m in matchups]
		wins = [(m.num_wins if m is not None else None) for m in matchups]
		ties = [(m.num_ties if m is not None else None) for m in matchups]
		losses = [(m.num_losses if m is not None else None) for m in matchups]
		ranks = [(m.avg_rank if m is not None else None) for m in matchups]

		def _win_rate_color(win_rate: Optional[float]) -> str:
			if win_rate is None:
				return RESET_ALL
			assert 0.0 <= win_rate <= 1.0
			if win_rate <= 0.2:
				return colorama.Fore.RED
			elif win_rate <= 0.4:
				return colorama.Fore.YELLOW
			elif win_rate <= 0.6:
				return colorama.Style.RESET_ALL
			elif win_rate <= 0.8:
				return colorama.Fore.GREEN
			else:
				return colorama.Fore.BLUE

		colors = [_win_rate_color(r) for r in win_rates]

		def _fmt_val(val, pct) -> str:
			if val is None:
				return ' ' * 5
			elif pct:
				return f'{int(round(val*100)):3} %'
			elif isinstance(val, int):
				return f'{val:5}'
			else:
				return f'{val:5.2f}'

		def _fmt_vals(vals, pct=False) -> list[str]:
			return [color + _fmt_val(val, pct=pct) + RESET_ALL for color, val in zip(colors, vals)]

		print(f'{right_pad(player.name, name_len)} | ' + ' | '.join(_fmt_vals(win_rates, pct=True)) + ' |')
		if print_full_matchups:
			print(f'{" " * name_len} | ' + ' | '.join(_fmt_vals(wins)) + ' |')
			print(f'{" " * name_len} | ' + ' | '.join(_fmt_vals(ties)) + ' |')
			print(f'{" " * name_len} | ' + ' | '.join(_fmt_vals(losses)) + ' |')
		print(f'{" " * name_len} | ' + ' | '.join(_fmt_vals(ranks)) + ' |')
		print(separator)


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
	g.add_argument('-p', '--players', default=None, dest='num_players', type=int, help='Number of players, or 0 for random per game. Default 4 if less than 100 games, 0 if >= 100')
	g.add_argument('--seed', type=int, help='Deterministic random seed (currently only works for single-threaded)')
	g.add_argument('--short', action='store_true', help='Play very short game (1 round of 3 cards)')

	g = parser.add_argument_group('Alternate game rules')
	g.add_argument('--pudding',    metavar='0/1', default=True, type=_bool_arg, help='Use pudding - Default 1')
	g.add_argument('--chopsticks', metavar='0/1', default=True, type=_bool_arg, help='Use chopsticks - Default 1')
	g.add_argument('--omniscient', metavar='0/1', default=None, type=_bool_arg, help='Omniscient mode (all players see all cards) - Default 0, or 1 if --short')

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

	# number of players

	if args.num_players is None:
		if args.num_games < 100:
			args.num_players = 4
		else:
			print('100 games or more; randomizing player count per game')
			args.num_players = 0

	# Don't check max here, that will be checked later on in Game constructor (in case we support future variants with more than 5 players)
	if (args.num_players < 0) or (args.num_players == 1):
		raise ValueError(f'Invalid number of players: {args.num_players}')

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
	print(f'{len(player_names)} Players: ' + ', '.join(player_names))
	# TODO: also print if will randomize selected players and/or player count per game

	deck_dist = _get_deck_distribution(args)

	play_game_kwargs = dict(
		num_players=args.num_players,
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

	# TODO: return partial results if exiting early (need to use multiprocessing shared array for returns)

	if use_multiprocessing:
		with Pool() as p:
			processes = p._processes  # TODO: is there a better way to get this without using private members?
			chunksize = ceil_divide(args.num_games, processes)
			assert chunksize >= 1
			chunksize = min(chunksize, MULTIPROCESSING_MAX_CHUNK_SIZE)
			game_results = list(tqdm(
				p.imap(
					_play_game_from_kwargs,
					itertools.repeat(play_game_kwargs, args.num_games),
					chunksize=chunksize,
				),
				total=args.num_games,
				desc=f'Playing {args.num_games} games ({processes} processes, chunksize {chunksize})',
			))
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
