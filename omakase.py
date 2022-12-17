#!/usr/bin/env python

import argparse

from cards import Cards
from deck import Deck, get_deck_distribution
from game import Game


def _bool_arg(val) -> bool:
	return bool(int(val))


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-p', '--players', default=4, type=int, help='Number of players')
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

	kwargs = dict(
		num_players=args.players,
		deck_dist=deck_dist,
		omniscient=args.omniscient,
	)

	if args.short:
		kwargs['num_rounds'] = 1
		kwargs['num_cards_per_player'] = 3

	game = Game(**kwargs)
	game.play()


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
