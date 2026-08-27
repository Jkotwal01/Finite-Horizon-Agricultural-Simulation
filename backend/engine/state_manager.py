"""
engine/state_manager.py — StateManager (FR-003).

Maintains current + previous state and calculates deltas.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.state import CanonicalState, TimeState, MemoryState
import config as cfg


class StateManager:
    """
    Maintains the persistent memory of the simulation.

    Rules (FR-003, BR-012):
    - Previous observation is stored separately (never mutated).
    - Deltas are computed N→N+1.
    - First observation has safe empty history.
    """

    def __init__(self) -> None:
        self.current: CanonicalState | None = None
        self.memory: MemoryState = MemoryState()
        self.time_state: TimeState | None = None

    def update(self, state: CanonicalState) -> MemoryState:
        """
        Accept a new canonical state, compute deltas, return updated memory.
        """
        self.memory.update(state)
        self.current = state
        self.time_state = TimeState.from_turn(
            turn=state.turn,
            total_turns=cfg.TOTAL_TURNS,
            turns_per_day=cfg.TURNS_PER_DAY,
            endgame_threshold=cfg.ENDGAME_THRESHOLD,
        )
        # append to history
        self.memory.turn_history.append({
            "turn": state.turn,
            "cash": state.cash,
            "shed_total": sum(state.shed_inventory.values()),
        })
        return self.memory

    def get_time_state(self) -> TimeState:
        if self.time_state is None:
            raise RuntimeError("StateManager has not been updated yet.")
        return self.time_state

    def is_endgame(self) -> bool:
        return self.time_state is not None and self.time_state.is_endgame

    def remaining_turns(self) -> int:
        if self.time_state is None:
            return cfg.TOTAL_TURNS
        return self.time_state.remaining_turns
