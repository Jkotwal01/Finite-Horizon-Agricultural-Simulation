"""
models/report.py — EvaluationReport and TerminalResult data classes.

FR-021 Telemetry, FR-022 Terminal Objective.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationReport:
    """
    Recorded per-run metrics for analysis and release gating.

    Section 8 minimum fields: turns, exceptions, invalid_actions,
    terminal_wealth, timing_ms, forecast_error, loss_events.
    """
    turns: int = 0
    exceptions: int = 0
    invalid_actions: int = 0
    terminal_wealth: float = 0.0
    timing_ms: dict[str, float] = field(default_factory=dict)
    forecast_error: dict[str, Any] = field(default_factory=dict)
    loss_events: dict[str, int] = field(default_factory=dict)
    # additional telemetry
    action_log: list[dict] = field(default_factory=list)
    per_turn_wealth: list[float] = field(default_factory=list)
    crop_deaths: int = 0
    animal_deaths: int = 0
    warehouse_overflows: int = 0
    replans: int = 0

    def record_action(self, turn: int, action: dict, result: str,
                      error: str = "") -> None:
        self.action_log.append({
            "turn": turn,
            "action": action,
            "result": result,
            "error": error,
        })

    def to_dict(self) -> dict:
        return {
            "turns": self.turns,
            "exceptions": self.exceptions,
            "invalid_actions": self.invalid_actions,
            "terminal_wealth": self.terminal_wealth,
            "timing_ms": self.timing_ms,
            "forecast_error": self.forecast_error,
            "loss_events": self.loss_events,
            "action_log": self.action_log[-50:],  # last 50 for API responses
            "per_turn_wealth": self.per_turn_wealth,
            "crop_deaths": self.crop_deaths,
            "animal_deaths": self.animal_deaths,
            "warehouse_overflows": self.warehouse_overflows,
        }


@dataclass
class TerminalResult:
    """
    Final score object produced at Turn 720.

    terminal_wealth = cash + inventory_value + asset_value - penalties
    """
    turn: int = 0
    terminal_wealth: float = 0.0
    cash: float = 0.0
    inventory_value: float = 0.0     # sellable inventory at market price
    asset_value: float = 0.0         # structures, land
    penalties: float = 0.0           # dead crops, illegal actions, etc.
    unrealizable_production: float = 0.0  # crops maturing after turn 720 → $0
    exceptions: int = 0
    invalid_actions: int = 0
    component_ledger: dict = field(default_factory=dict)

    def compute(self) -> float:
        """Deterministically compute terminal wealth from components."""
        self.terminal_wealth = (
            self.cash
            + self.inventory_value
            + self.asset_value
            - self.penalties
        )
        # unrealizable_production does NOT count toward terminal_wealth
        self.component_ledger = {
            "cash": self.cash,
            "inventory_value": self.inventory_value,
            "asset_value": self.asset_value,
            "penalties": self.penalties,
            "unrealizable_production": self.unrealizable_production,
            "terminal_wealth": self.terminal_wealth,
        }
        return self.terminal_wealth

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "terminal_wealth": round(self.terminal_wealth, 2),
            "cash": round(self.cash, 2),
            "inventory_value": round(self.inventory_value, 2),
            "asset_value": round(self.asset_value, 2),
            "penalties": round(self.penalties, 2),
            "unrealizable_production": round(self.unrealizable_production, 2),
            "exceptions": self.exceptions,
            "invalid_actions": self.invalid_actions,
            "component_ledger": {
                k: round(v, 2) for k, v in self.component_ledger.items()
            },
        }
