# Python Poker Solver

A postflop solver written in python.

Uses counterfactual regret to create nash equilibrium strategy.

## Current state

Currently this solver works on river subgames, uses no information abstraction, and is very slow.

## Currently working on
 - Testing CFR vs MCCFR
 - Reducing tree size via information abstraction
 - Testing effectiveness of regret-based pruning
 - Testing effectiveness of discounting
