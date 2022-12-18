#!/usr/bin/env python

import argparse
from dataclasses import dataclass, field
import itertools
from multiprocessing import Pool
import random
from typing import List

from tqdm import tqdm, trange

from ai import RandomAI, RandomPlusAI
from simpleai import SimpleAI

from cards import Cards
from deck import Deck, get_deck_distribution
from elo import multiplayer_elo, DEFAULT_ELO
from game import Game
from player import get_player_name


def _bool_arg(val) -> bool:
	return bool(int(val))


@dataclass
class PlayerGameStats:
	name: str
	total_num_points: int = 0
	margin_from_winner: int = 0
	ranks: List[int] = field(default_factory=list)
	elo: float = DEFAULT_ELO


def play_game(game_kwargs):

	random.seed()

	# TODO: randomize order of players
	# TODO: once there are stateful AI, will need to create new ones each game
	game = Game(**game_kwargs)
	return game.play()


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-p', '--players', default=4, type=int, help='Number of players')
	parser.add_argument('-n', '--num-games', default=1, type=int, help='Number of games to play')
	parser.add_argument('--short', action='store_true', help='Play very short game (1 round of 3 cards)')
	parser.add_argument('--pudding',    metavar='0/1', default=True,  type=_bool_arg, help='Use pudding')
	parser.add_argument('--chopsticks', metavar='0/1', default=False, type=_bool_arg, help='Use chopsticks')
	parser.add_argument('--omniscient', metavar='0/1', default=True,  type=_bool_arg, help='Omniscient mode (all players see all cards)')
	args = parser.parse_args()

	deck_dist = get_deck_distribution()

	if not args.pudding:
		deck_dist[Cards.Pudding] = 0

	if not args.chopsticks:
		deck_dist[Cards.Chopsticks] = 0

	ai = [SimpleAI(), RandomPlusAI()]
	player_names = ['SimpleAI', 'RandomPlusAI']

	num_random_ai = args.players - len(ai)
	ai.extend([RandomAI() for _ in range(num_random_ai)])
	if num_random_ai == 1:
		player_names.append('RandomAI')
	else:
		player_names.extend([f'RandomAI {1+idx}' for idx in range(num_random_ai)])

	game_kwargs = dict(
		num_players=args.players,
		deck_dist=deck_dist,
		omniscient=args.omniscient,
		player_names=player_names,
		verbose=(args.num_games == 1),
		ai=ai,
	)

	if args.short:
		game_kwargs['num_rounds'] = 1
		game_kwargs['num_cards_per_player'] = 3

	player_game_stats = [PlayerGameStats(name=name) for name in player_names]

	if args.num_games == 1:
		play_game(game_kwargs)
		return

	print(f'{args.players} Players: ' + ', '.join(player_names))

	use_multiprocessing = args.num_games > 10

	if use_multiprocessing:
		with Pool() as p:
			game_results = list(
				tqdm(
					p.imap(play_game, itertools.repeat(game_kwargs, args.num_games)),
					total=args.num_games,
					desc=f'Playing {args.num_games} games (multithreaded)',
				)
			)
	else:
		game_results = []
		for _ in trange(args.num_games, desc=f'Playing {args.num_games} games'):
			game_results.append(play_game(game_kwargs))

	for game_idx, result in enumerate(tqdm(game_results, desc='Processing results')):
		if len(result) != args.players:
			raise ValueError(f'Game did not return expected length of results ({len(result)} != {args.players})')

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

	print()
	print(f'Results from {args.num_games} games')
	print()
	# TODO: dynamic table column widths, in case of long player name or player with >= 10,000 wins
	print(f'{"Player":<16} | {"Wins":^10} | Avg rank | Avg score | Avg margin | Elo')
	print(f'{"-"*16} | {"-"*10} | {"-"*8} | {"-"*9} | {"-"*10} | {"-"*4}')
	for player in player_game_stats:
		num_wins = sum(rank == 1 for rank in player.ranks)
		pct_wins = num_wins / args.num_games * 100.0
		avg_rank = sum(player.ranks) / args.num_games
		avg_score = player.total_num_points / args.num_games
		avg_margin = player.margin_from_winner / args.num_games
		print(f'{player.name:<16} |{num_wins:>5} ={pct_wins:3.0f}% | {avg_rank:>8.2f} | {avg_score:>9.2f} | {avg_margin:>10.2f} | {player.elo:>4.0f}')


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
"""
