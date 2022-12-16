import cards
from deck import *
from ai import *
from simpleai import *
import game

use_pudding = True
use_chopsticks = False


def play_short_game(num_players=4):
	deck_dist = get_deck_distribution()

	if not use_pudding:
		deck_dist[Cards.Pudding] = 0

	if not use_chopsticks:
		deck_dist[Cards.Chopsticks] = 0

	omniscient = True
	#omniscient = False

	game.play_game(num_players=num_players, num_rounds=1, deck_dist=deck_dist, num_cards_per_player=3, omniscient=omniscient)


def play_full_game(num_players=4):
	deck_dist = get_deck_distribution()

	if not use_pudding:
		deck_dist[Cards.Pudding] = 0

	if not use_chopsticks:
		deck_dist[Cards.Chopsticks] = 0

	game.play_game(num_players=num_players, deck_dist=deck_dist)


def main():
	play_full_game()
	#play_short_game()


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
