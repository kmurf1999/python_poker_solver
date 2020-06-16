from poker import Card
from poker.hand import Range
from copy import deepcopy

PLAYER_1_ID = 0
PLAYER_2_ID = 1
CHANCE_ID = 2
TERMINAL_ID = 3

DECK_SIZE = 52

# cards are 0->51
BET = 52
CALL = 53
FOLD = 54
CHECK = 55
PLAYER_ACTIONS = [BET, CALL, FOLD, CHECK]

PREFLOP = 0
FLOP = 1
TURN = 2
RIVER = 3

p1_range = Range('JJ+ AJ+ KJ+ QJ+')
p2_range = Range('JJ+ AJ+ KJ+ QJ+')

def copy_cards(deck):
    new_deck = []
    for c in deck:
        new_deck.append(Card(c))
    return new_deck

class PlayerState:
    def __init__(self):
        # current number of chips
        self._stack = 1000

        # current cards
        self._hand = None
        # current wager
        self._wager = 0
        self._has_folded = False

    def __str__(self):
        return f"hand: {self._hand} stack: {self._stack} wager: {self._wager}"

    @property
    def is_allin(self): return self._stack == 0

    @property
    def has_folded(self): return self._has_folded

# poker game state
class State:
    def __init__(self):
        # current player index (0 oop, 1 ip)
        # 2 chance node, 3 terminal node
        self._current = CHANCE_ID

        # TODO better intialization
        self._players = [PlayerState(), PlayerState()]

        # current number of chips in pot
        self._pot = 100

        self._street = RIVER

        # action sequence
        self._history = ""

        # create empty deck
        self._deck = list(Card)

        # legal actions start as cards to draw
        self._legal_actions = list(range(DECK_SIZE))

        # array of ints for now
        self._board = []

    def copy(self):
        """Copy state and return"""
        new_state = State()
        new_state._current = self._current
        new_state._players = deepcopy(self._players)
        new_state._pot = self._pot
        new_state._street = self._street
        new_state._history = self._history
        new_state._deck = copy_cards(self._deck)
        new_state._legal_actions = deepcopy(self._legal_actions)
        new_state._board = copy_cards(self._board)
        return new_state

    # TEMPORARY
    def set_board(self, board):
        self._board = board
        for c in board:
            self._deck.remove(c)
        self._update_node_type()

    def __str__(self):
        return f"""history: {self._history} pot: {self._pot}, board: {self._board}
    player 1: {self._players[0]}
    player 2: {self._players[1]}"""

    @property
    def current(self):
        """Return current ID
        Could be player id, chance node, or terminal node
        """
        return self._current

    @property
    def current_player(self):
        assert(not self.is_chance)
        assert(not self.is_terminal)
        return self._players[self._current]

    @property
    def other_player(self):
        assert(not self.is_chance)
        assert(not self.is_terminal)
        return self._players[1 - self._current]

    @property
    def is_chance(self): return self._current == CHANCE_ID

    @property
    def is_terminal(self): return self._current == TERMINAL_ID

    @property
    def history(self): return self._history

    def infoset_str(self, player):
        """Return str repr of hole cards for player + history"""
        return str(player)+' '+str(self._players[player]._hand)+' '+self.history

    def _is_player_action_valid(self, action) -> bool:
        """return true if the action is valid for the current state"""
        if action == BET:
            # can bet if other player has not
            if self.other_player._wager == 0: return True
            return False
        if action == CHECK:
            # can check if other player has not bet
            if self.other_player._wager == 0: return True
            return False
        if action == CALL:
            # can call only if other player has bet
            if self.other_player._wager == 0: return False
            return True
        if action == FOLD:
            # can fold only if other player has bet
            if self.other_player._wager == 0: return False
            return True

    @property
    def legal_actions(self):
        """Return legal actions to take"""
        return self._legal_actions

    def _legal_dealings(self):
        global p1_range, p2_range
        actions = [] # possible indexes to choose from in ranges
        # player 1 legal dealing
        if self._players[0]._hand == None:
            for (i, combo) in enumerate(p1_range.combos):
                if not combo.first in self._deck: continue
                if not combo.second in self._deck: continue
                actions.append(i)
            return actions
        # player 2 legal dealings
        elif self._players[1]._hand == None:
            for (i, combo) in enumerate(p2_range.combos):
                if not combo.first in self._deck: continue
                if not combo.second in self._deck: continue
                actions.append(i)

        return actions

    def _calc_legal_actions(self) -> list:
        """Get all legal actions and return array of
        action ids"""
        # no actions to take
        if self.is_terminal: return []

        if self.is_chance:
            return self._legal_dealings()

        # player actions
        actions = []
        for action in PLAYER_ACTIONS:
            if self._is_player_action_valid(action):
                actions.append(action)
        return actions

    def _update_node_type(self):
        """
        Update current node type and legal actions
        """
        # if was terminal, then it hasn't changed
        if self.current == TERMINAL_ID:
            self._legal_actions = self._calc_legal_actions()
            return

        for p in self._players:
            if p.has_folded or p.is_allin:
                # if player has folded or is all in,
                # we are in a terminal state
                self._current = TERMINAL_ID
                self._legal_actions = self._calc_legal_actions()
                return

        # check if we still need to deal
        for p in self._players:
            if p._hand == None:
                self._current = CHANCE_ID
                self._legal_actions = self._calc_legal_actions()
                return

        # otherwise, its a player id node type
        # which we'll update in apply_action
        self._legal_actions = self._calc_legal_actions()
        return

    def _next_street(self):
        """Transition to next street or detect terminal state"""
        if self._street == RIVER:
            self._current = TERMINAL_ID
            return

        for p in self._players:
            if p.has_folded or p.is_allin:
                self._current = TERMINAL_ID
                return

        # TODO add deal cards
        self._street += 1
        self._current = PLAYER_1_ID
        return

    def apply_action(self, action):
        """
        Apply action and return new state
        @param action: BET, CHECK, CALL, ...
        @param action: if chance node, then index of chance outcome
        """
        action = int(action)
        if self.is_terminal: return
        if self.is_chance:
            # apply chance action
            # action is index of combo in player range
            for (i, p) in enumerate(self._players):
                if p._hand == None:
                    # update history
                    self._history += 'd'
                    # add card to hand
                    p._hand = action
                    # remove card
                    if i == 0:
                        c1 = p1_range.combos[action].first
                        c2 = p1_range.combos[action].second
                        self._deck.remove(c1)
                        self._deck.remove(c2)
                    else:
                        c1 = p2_range.combos[action].first
                        c2 = p2_range.combos[action].second
                        self._deck.remove(c1)
                        self._deck.remove(c2)
                    # calculate node type
                    self._current = PLAYER_1_ID
                    self._update_node_type()
                    return
        # apply player action
        if action == CHECK:
            self._history += 'x'
            if self.current == PLAYER_1_ID:
                self._current = PLAYER_2_ID
            else:
                # transition to next street
                self._next_street()

        if action == BET:
            self._history += 'b'
            # if has enough chips to bet pot without going all in
            if self.current_player._stack >= self._pot:
                self.current_player._wager += self._pot
            else:
                self.current_player._wager += self.current_player._stack

            self.current_player._stack -= self.current_player._wager
            self._pot += self.current_player._wager
            # current player id is now other player
            self._current = 1 - self.current

        if action == CALL:
            self._history += 'c'
            other_wager = self.other_player._wager
            if self.current_player._stack < other_wager:
                # calculate difference, give other player chips back
                diff = other_wager - self.current_player._stack
                self.other_player._stack += diff
                # pot should now be 2x current player stack
                self._pot = 2 * self.current_player.stack
                self.current_player._stack = 0
            else:
                self._pot += other_wager
                self.current_player._stack -= other_wager

            # remove other wager
            self.other_player._wager = 0
            # transition to next street
            self._next_street()

        if action == FOLD:
            self._history += 'f'
            # calculate diffence between bets
            diff = self.other_player._wager - self.current_player._wager
            self._pot -= diff
            self.other_player._stack += diff
            # transition to next street
            self._next_street()

        self._update_node_type()

    # return a tuple of utility
    def get_utility(self) -> (float, float):
        global p1_range, p2_range
        # needs to be terminal
        if not self.is_terminal: return (0, 0)
        value = self._pot / 2.0
        # check for folds
        if self._players[0].has_folded:
            return (-value, value)
        if self._players[1].has_folded:
            return (value, -value)
        # evaluate showdown
        p1_hand = p1_range.combos[self._players[0]._hand]
        p1_hand = [p1_hand.first, p1_hand.second] + self._board

        p2_hand = p2_range.combos[self._players[1]._hand]
        p2_hand = [p2_hand.first, p2_hand.second] + self._board

        if p1_hand == p2_hand: return (0, 0)
        elif p1_hand > p2_hand:
            return (value, -value)
        else:
            return (-value, value)

