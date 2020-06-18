import numpy as np
import random
from poker.hand import Range

from state import State, PlayerState

class ISet:
    """Infoset node"""
    def __init__(self, n_actions):
        self.regrets = np.zeros(n_actions)
        self.strategy_sum = np.zeros(n_actions)

    def get_final_strategy(self):
        """Get normalized strategy from strategy_sum"""
        norm_sum = 0
        strategy = np.zeros(len(self.strategy_sum))
        for a in range(len(self.strategy_sum)):
            norm_sum += max(self.strategy_sum[a], 0)
        for a in range(len(self.strategy_sum)):
            if norm_sum > 0:
                strategy[a] = max(self.strategy_sum[a], 0) / norm_sum
            else:
                strategy[a] = 1 / len(self.strategy_sum)
        return strategy

    def get_strategy(self):
        """Get strategy for infoset through regret matching"""
        norm_sum = 0
        strategy = np.zeros(len(self.regrets))
        for a in range(len(self.regrets)):
            norm_sum += max(self.regrets[a], 0)
        for a in range(len(self.regrets)):
            if norm_sum > 0:
                strategy[a] = max(self.regrets[a], 0) / norm_sum
            else:
                strategy[a] = 1 / len(self.regrets)
        return strategy


class CFRTrainerBase:
    """Base class for different cfr variants"""
    def __init__(self, initial_state):
        self._initial_state = initial_state
        self._infosets = dict()


    def get_or_create(self, key, n_actions):
        """Get or create infoset node"""
        try:
            return self._infosets[key]
        except:
            self._infosets[key] = ISet(n_actions)
            return self._infosets[key]

class MCCFRTrainer(CFRTrainerBase):
    """external sampling cfr implementation"""
    def __init__(self, initial_state, discount=False, pruning=False):
        super().__init__(initial_state)
        # for profiling
        self._nodes_touched = 0
        # options
        self._discount = discount
        self._pruning = pruning
        # hyper params
        self._d_interval = 1000 # discount interval
        self._prune_threshold = 10000

    @property
    def discount(self):
        return self._discount

    def train(self, T):
        for t in range(1, T):
            for player in [0, 1]:
                if self._pruning and t > self._prune_threshold:
                    q = random.uniform(0, 1)
                    if q < 0.05: # 5% of the time, don't prune
                        self.mccfr(self._initial_state, player, 1)
                    else:
                        self.mccfr(self._initial_state, player, 1, prune=True)
                else:
                    self.mccfr(self._initial_state, player, 1)

            if self.discount:
                # perform discounting
                if t % self._d_interval == 0:
                    # discount factor
                    d = (t / self._d_interval) / ((t / self._d_interval) + 1)
                    for k in self._infosets:
                        self._infosets[k].regrets *= d
                        self._infosets[k].strategy_sum *= d

    def mccfr(self, state, player, cfr_reach, prune=False) -> float:
        self._nodes_touched += 1
        if state.is_terminal:
            return state.get_utility()[player]
        if state.is_chance:
            # sample one chance outcome
            chances = state.legal_actions
            chance_prob = 1 / len(chances)
            child_state = state.apply_action(random.choice(chances))
            return self.mccfr(child_state, player, cfr_reach * chance_prob)

        actions = state.legal_actions
        iset = self.get_or_create(state.infoset_str(state.current), len(actions))
        sigma = iset.get_strategy()

        if state.current == player:
            util = 0
            utils = np.zeros(len(actions))
            for (i, action) in enumerate(actions):
                child_state = state.apply_action(action)
                utils[i] = self.mccfr(child_state, player, cfr_reach)
                util += utils[i] * sigma[i]

            # update regrets & strategy sum
            for (i, _) in enumerate(actions):
                iset.regrets[i] += cfr_reach * (utils[i] - util)
                iset.strategy_sum[i] += cfr_reach * sigma[i]

            return util

        else: # sample a single action
            a_idx = np.random.choice(list(range(len(actions))), 1, p=sigma)[0]
            child_state = state.apply_action(actions[a_idx])
            child_cfr_reach = sigma[a_idx] * cfr_reach

            return self.mccfr(child_state, player, child_cfr_reach)


class CFRTrainer(CFRTrainerBase):
    """vanilla cfr implementation"""
    def __init__(self, initial_state):
        super().__init__(initial_state)
        # for profiling
        self._nodes_touched = 0

    def train(self, T):
        """
        @param T: iteration count
        """
        for t in range(1, T):
            for player in [0, 1]:
                self.cfr(self._initial_state, player, 1)

    def cfr(self, state, player, cfr_reach) -> float:
        """Recursive cfr function
            @param state: current state value
            @param player: index of player (0 or 1)
            @param cfr_reach: counter-factual probability of reaching current state
            @return utility: ev of node
        """
        self._nodes_touched += 1
        if state.is_terminal:
            return state.get_utility()[player]
        if state.is_chance:
            util = 0
            # get all chance outcomes
            actions = state.legal_actions
            # assign equal probability to each action
            cfr_reach /= len(state.legal_actions)
            for c in actions:
                child_state = state.apply_action(c)
                util += self.cfr(child_state, player, cfr_reach)
            return util

        actions = state.legal_actions
        iset = self.get_or_create(state.infoset_str(state.current), len(actions))
        # get strategy by regret matching
        sigma = iset.get_strategy()
        util = 0
        utils = np.zeros(len(actions))
        for (i, action) in enumerate(actions):
            child_state = state.apply_action(action)
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
