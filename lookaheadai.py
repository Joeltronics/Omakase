from ai import Ai
from player import PlayerState
from cards import *
from utils import *


class LookaheadAi(Ai):

	def __init__(self, player_state, total_num_players):
		super(LookaheadAi, self).__init__(player_state, total_num_players)

	def get_ai_name(self):
		return "Lookahead AI"

	def select_card(self, hand, verbose=False):
		# TODO
		pass

