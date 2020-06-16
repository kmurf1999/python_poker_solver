import numpy as np
from poker.hand import Range
from poker import Card, Combo

from state import State, PlayerState

class ISet:
    """Infoset node"""
    def __init__(self, n_actions):
        self.regrets = np.zeros(n_actions)
        self.strategy_sum = np.zeros(n_actions)

def get_final_strategy(iset):
    """Get normalized strategy from strategy_sum"""
    norm_sum = 0
    strategy = np.zeros(len(iset.strategy_sum))
    for a in range(len(iset.strategy_sum)):
        norm_sum += max(iset.strategy_sum[a], 0)
    for a in range(len(iset.strategy_sum)):
        if norm_sum > 0:
            strategy[a] = max(iset.strategy_sum[a], 0) / norm_sum
        else:
            strategy[a] = 1 / len(iset.strategy_sum)
    return strategy

def get_strategy(iset):
    """Get strategy for infoset through regret matching"""
    norm_sum = 0
    strategy = np.zeros(len(iset.regrets))
    for a in range(len(iset.regrets)):
        norm_sum += max(iset.regrets[a], 0)
    for a in range(len(iset.regrets)):
        if norm_sum > 0:
            strategy[a] = max(iset.regrets[a], 0) / norm_sum
        else:
            strategy[a] = 1 / len(iset.regrets)
    return strategy


class CFRTrainer:
    def __init__(self, initial_state):
        self._initial_state = initial_state
        self._infosets = dict()

    def train(self, T):
        """
        @param T: iteration count
        """
        utils = np.array([0, 0])
        for t in range(1, T):
            for player in [0, 1]:
                utils[player] = self.cfr(self._initial_state, player, 1)
            print(sum(utils))

    def get_or_create(self, key, n_actions):
        """Get or create infoset node"""
        try:
            return self._infosets[key]
        except:
            self._infosets[key] = ISet(n_actions)
            return self._infosets[key]

    def cfr(self, state, player, cfr_reach) -> float:
        """Recursive cfr function
            @param state: current state value
            @param player: index of player (0 or 1)
            @param cfr_reach: counter-factual probability of reaching current state
            @return utility: ev of node
        """
        if state.is_terminal:
            return state.get_utility()[player]
        if state.is_chance:
            util = 0
            # get all chance outcomes
            actions = state.legal_actions
            # assign equal probability to each action
            cfr_reach /= len(state.legal_actions)
            for c in actions:
                child_state = state.copy()
                child_state.apply_action(c)
                util += self.cfr(child_state, player, cfr_reach)
            return util

        actions = state.legal_actions
        iset = self.get_or_create(state.infoset_str(state.current), len(actions))
        # get strategy by regret matching
        sigma = get_strategy(iset)
        util = 0
        utils = np.zeros(len(actions))
        for (i, action) in enumerate(actions):
            child_state = state.copy()
            child_state.apply_action(action)
            # update reach probs
            child_cfr_reach = cfr_reach
            if state.current != player:
                child_cfr_reach *= sigma[i]
            utils[i] = self.cfr(child_state, player, child_cfr_reach)
            util += utils[i] * sigma[i]

        # if not doing simultanuous updates
        if state.current != player:
            return util

        # update regrets & strategy sum
        for (i, _) in enumerate(actions):
            iset.regrets[i] += cfr_reach * (utils[i] - util)
            iset.strategy_sum[i] += cfr_reach * sigma[i]

        return util

board = [Card('4c'), Card('6s'), Card('Ts'), Card('3d'), Card('5s')]

init_state = State()
init_state.set_board(board)

p1_range = Range('JJ+ AJ+ KJ+ QJ+')
p2_range = Range('JJ+ AJ+ KJ+ QJ+')

trainer = CFRTrainer(init_state)
trainer.train(10)

for k in trainer._infosets:
    player, card, hist = k.split(' ')
    if player == '0':
        print(hist, p1_range.combos[int(card)], get_final_strategy(trainer._infosets[k]))

        # print(v, infosets[v].strategy_sum)
