"""
models/plan.py — Plan and EndgamePlan data classes.

FR-019 Counterfactual Replanning, FR-020 Endgame.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Plan:
    """
    Strategic plan produced by the strategy engine.
    Includes baseline vs candidate terminal wealth for counterfactual comparison.
    """
    actions: list[dict] = field(default_factory=list)
    reason: str = ""
    expected_terminal_value: float = 0.0
    baseline_terminal_value: float = 0.0
    improvement: float = 0.0
    signature: str = ""          # hash of plan for oscillation detection
    replan_count: int = 0

    def compute_signature(self) -> str:
        """Create a reproducible string signature of this plan."""
        action_str = ";".join(
            f"{a.get('kind','')}-{a.get('target','')}" for a in self.actions
        )
        self.signature = str(hash(action_str))
        return self.signature

    def to_dict(self) -> dict:
        return {
            "actions": self.actions,
            "reason": self.reason,
            "expected_terminal_value": self.expected_terminal_value,
            "baseline_terminal_value": self.baseline_terminal_value,
            "improvement": self.improvement,
            "signature": self.signature,
            "replan_count": self.replan_count,
        }


@dataclass
class EndgamePlan:
    """
    Endgame liquidation plan (FR-020): harvest, collect, sell.
    """
    viable_crops: list[dict] = field(default_factory=list)
    non_viable_crops: list[dict] = field(default_factory=list)
    harvest_actions: list[dict] = field(default_factory=list)
    sell_actions: list[dict] = field(default_factory=list)
    expected_final_cash: float = 0.0
    is_final_turn: bool = False

    def to_dict(self) -> dict:
        return {
            "viable_crops": self.viable_crops,
            "non_viable_crops": self.non_viable_crops,
            "harvest_actions": self.harvest_actions,
            "sell_actions": self.sell_actions,
            "expected_final_cash": self.expected_final_cash,
            "is_final_turn": self.is_final_turn,
        }
