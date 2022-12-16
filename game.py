import cards
from deck import *
from player import *
from ai import *
from simpleai import *
import scoring


def get_num_cards_per_player(num_players):
	if num_players == 2:
		return 10
	elif num_players == 3:
		return 9
	elif num_players == 4:
		return 8
	elif num_players == 5:
		return 7
	else:
		print("Invalid number of players: %i") % num_players
		assert False


def play_game(num_players=4, num_rounds=3, deck_dist=None, num_cards_per_player=None, omniscient=False):

	if not num_cards_per_player:
		num_cards_per_player = get_num_cards_per_player(num_players)

	if not deck_dist:
		deck_dist = get_deck_distribution()

	print('Creating & shuffling deck')

	deck = Deck(deck_dist)

	print('Creating players with simple AI')
	player_states = [PlayerState(deck_dist) for _ in range(num_players)]
	ais = [simple_ai for _ in range(num_players)]

	print("Players: " + ", ".join([player.name for player in player_states]))
	print()

	print('Starting game')
	print()

	for round_num in range(num_rounds):

		is_forward_round = (round_num % 2 == 0)

		if num_rounds > 1:
			print('==== Round %i =====' % (round_num+1))

		hands = deck.deal_hands(num_players, num_cards_per_player)

		print("Dealing hands:")
		for player, hand in zip(player_states, hands):
			player.assign_hand(hand)
			print("\t%s: %s" % (player.name, cards.card_names(player.hand)))
		print()

		init_other_player_states(player_states, forward=is_forward_round, omniscient=omniscient)

		for turn in range(num_cards_per_player):

			print('--- Turn %i ---' % (turn+1))
			print()

			for n, (player, ai) in enumerate(zip(player_states, ais)):

				verbose = (n == 0)

				print(player.name)
				print("Hand: %s" % cards.card_names(player.hand))
				pudding_str = (" (%i pudding)" % player.num_pudding) if player.num_pudding else ""
				print("Plate: %s%s" % (cards.card_names(player.plate, sort=True), pudding_str))

				if verbose:
					print("State:")
					print(repr(player))

				card = ai(player, player.hand, verbose=verbose)

				player.play_card(card)
				print("Plays: %s" % cards.card_name(card))
				print()

			debug_update_player_state_verbose = False

			for n, player in enumerate(player_states):
				verbose = debug_update_player_state_verbose and (n == 0)
				player.update_other_player_state_before_pass(verbose=verbose)

			print('Passing cards %s' % ('forward' if is_forward_round else 'backward'))
			pass_hands(player_states, forward=is_forward_round)

			for n, player in enumerate(player_states):
				verbose = debug_update_player_state_verbose and (n == 0)
				player.update_other_player_state_after_pass(verbose=verbose)

		scoring.score_round(player_states, print_it=True)

		print('Scores after round:')
		for player in player_states:
			print("\t%s: %i, %i pudding" % (player.name, player.total_score, player.num_pudding))
		print()

	scoring.score_puddings(player_states)


if __name__ == "__main__":
	play_game()
