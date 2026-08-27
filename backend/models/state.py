"""
models/state.py — Core game state data classes.

FR-001 CanonicalState, FR-002 TimeState, FR-003 MemoryState
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ── FR-001: Canonical game state ──────────────────────────────────────────────
@dataclass
class CanonicalState:
    """
    Normalised view of the environment for a single turn.
    Downstream modules always read from this; never from raw dicts.
    """
    turn: int
    day: int
    hour: int
    farms: list[dict]       # list of tile dicts {row, col, status, crop, ...}
    market: dict            # {product: {price, inventory, sold_this_turn}}
    shops: list[dict]       # [{name, products, demand}]
    town: dict              # {demand_events: [...]}
    rules: dict             # snapshot of config for this turn
    cash: float = 0.0
    workers: list[dict] = field(default_factory=list)
    structures: list[dict] = field(default_factory=list)
    shed_inventory: dict = field(default_factory=dict)   # {product: units}
    animals: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "day": self.day,
            "hour": self.hour,
            "cash": self.cash,
            "farms": self.farms,
            "market": self.market,
            "shops": self.shops,
            "town": self.town,
            "workers": self.workers,
            "structures": self.structures,
            "shed_inventory": self.shed_inventory,
            "animals": self.animals,
        }


# ── FR-002: Time / horizon state ──────────────────────────────────────────────
@dataclass
class TimeState:
    """Derived time information; remaining_turns is never negative."""
    turn: int
    day: int
    hour: int
    total_turns: int
    turns_per_day: int
    remaining_turns: int
    is_endgame: bool
    is_final_turn: bool

    @classmethod
    def from_turn(cls, turn: int, total_turns: int = 720,
                  turns_per_day: int = 24,
                  endgame_threshold: int = 670) -> "TimeState":
        day = turn // turns_per_day
        hour = turn % turns_per_day
        remaining = max(0, total_turns - turn)
        return cls(
            turn=turn,
            day=day,
            hour=hour,
            total_turns=total_turns,
            turns_per_day=turns_per_day,
            remaining_turns=remaining,
            is_endgame=(turn >= endgame_threshold),
            is_final_turn=(turn >= total_turns - 1),
        )

    def to_dict(self) -> dict:
        return self.__dict__


# ── FR-003: Persistent / memory state ────────────────────────────────────────
@dataclass
class MemoryState:
    """
    Carries the previous canonical state and computes deltas.
    Reservations persist until the corresponding action is observed.
    """
    previous: CanonicalState | None = None
    cash_delta: float = 0.0
    inventory_delta: dict[str, int] = field(default_factory=dict)
    production_delta: dict[str, int] = field(default_factory=dict)
    reserved_resources: dict[str, int] = field(default_factory=dict)  # {product: units}
    turn_history: list[dict] = field(default_factory=list)

    def update(self, current: CanonicalState) -> None:
        """Compute deltas between previous and current state."""
        if self.previous is None:
            self.cash_delta = 0.0
            self.inventory_delta = {}
            self.production_delta = {}
        else:
            self.cash_delta = current.cash - self.previous.cash
            # inventory delta per product
            for product in set(list(current.shed_inventory.keys()) +
                                list(self.previous.shed_inventory.keys())):
                cur_val = current.shed_inventory.get(product, 0)
                prv_val = self.previous.shed_inventory.get(product, 0)
                self.inventory_delta[product] = cur_val - prv_val
        self.previous = current

    def reserve(self, product: str, units: int) -> bool:
        """Reserve units; returns False if already fully reserved."""
        current_reserved = self.reserved_resources.get(product, 0)
        self.reserved_resources[product] = current_reserved + units
        return True

    def release(self, product: str, units: int) -> None:
        """Release a reservation after the action is confirmed."""
        current_reserved = self.reserved_resources.get(product, 0)
        self.reserved_resources[product] = max(0, current_reserved - units)

    def to_dict(self) -> dict:
        return {
            "cash_delta": self.cash_delta,
            "inventory_delta": self.inventory_delta,
            "production_delta": self.production_delta,
            "reserved_resources": self.reserved_resources,
            "history_length": len(self.turn_history),
        }
