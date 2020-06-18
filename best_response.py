from copy import deepcopy
import collections

from state import State

def _memoize_method(method):
  """Memoize a single-arg instance method using an on-object cache."""
  cache_name = "cache_" + method.__name__

  def wrap(self, arg):
    key = str(arg)
    cache = vars(self).setdefault(cache_name, {})
    if key not in cache:
      cache[key] = method(self, arg)
    return cache[key]

  return wrap

class BestResponsePolicy:
    def __init__(self, player_id, trainer):
        self._player_id = player_id

        self._root_state = trainer._initial_state
        # cfr trainer object
        self._trainer = trainer
        # dict of string->(state, cf_reach_prob)
        self._infosets = self.get_infosets(trainer._initial_state)

    def get_infosets(self, state):
        infosets = collections.defaultdict(list)
        for s, p in self.decision_nodes(state):
            infosets[s.infoset_str(self._player_id)].append((s, p))
        return infosets

    def decision_nodes(self, parent_state):
        """
        generator to traverse tree and yield (state, cfr_prob) pairs
        """
        if not parent_state.is_terminal:
            if parent_state.current == self._player_id:
                yield (parent_state, 1.0)
            for action, p_action in self.transitions(parent_state):
                for state, p_state in self.decision_nodes(
                        parent_state.apply_action(action)):
                    yield (state, p_state * p_action)

    def q_value(self, state, action):
        """
        Returns the value of the (state, action) to the best-responder.
        """
        return self.value(state.apply_action(action))

    def transitions(self, state):
        """
        Returns a list of (action cf prob pairs for the state)
        """
        if state.current == self._player_id:
            return [(action, 1.0) for action in state.legal_actions]
        elif state.is_chance:
            chance_outcomes = state.legal_actions
            n_outcomes = len(chance_outcomes)
            return [(outcome, 1.0 / n_outcomes) for outcome in chance_outcomes]
        else: # get average strategy of player and return probability dist of actions
            legal_actions = state.legal_actions
            # get current avg strategy for state
            action_probs = self._trainer.get_or_create(
                    state.infoset_str(state.current),
                    len(legal_actions)).get_final_strategy()
            return [(legal_actions[i], action_probs[i]) for i in range(len(action_probs))]

    @_memoize_method
    def best_response_action(self, infostate):
        infoset = self._infosets[infostate]
        return max(
                infoset[0][0].legal_actions,
                key=lambda a: sum(cf_p * self.q_value(s, a) for s, cf_p in infoset))

    @_memoize_method
    def value(self, state):
        """
        Main entry point
        Return value of state to best responder
        """
        if state.is_terminal:
            return state.get_utility()[self._player_id]
        elif state.current == self._player_id:
            action = self.best_response_action(
                    state.infoset_str(self._player_id))
            return self.q_value(state, action)
        else:
            return sum(
                    p * self.q_value(state, a) for a, p in self.transitions(state))

