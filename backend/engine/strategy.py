"""
engine/strategy.py — StrategyEngine (FR-010, FR-011, FR-019 stub).

Land economics, labor economics, and bounded counterfactual replanning.

Rules:
- BR-007: Actions evaluated against remaining usable turns.
- BR-008: Strategic purchases compared against a BUY vs WAIT baseline.
- BR-009: Bounded replanning with oscillation detection.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
from models.plan import Plan
import config as cfg


@dataclass
class LandPlan:
    action: str = "WAIT"         # "BUY" | "WAIT"
    cost: float = 0.0
    incremental_value: float = 0.0
    net_benefit: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class LaborPlan:
    action: str = "WAIT"         # "HIRE" | "WAIT"
    cost: float = 0.0
    marginal_contribution: float = 0.0
    net_benefit: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__


class StrategyEngine:
    """
    Evaluates land/labor investments and manages bounded replanning.
    """

    def __init__(self) -> None:
        self._plan_signatures: set[str] = set()
        self._replan_count: int = 0

    def evaluate_land(
        self,
        cash: float,
        remaining_turns: int,
        empty_tiles: int,
        avg_crop_value_per_turn: float = 2.0,
    ) -> LandPlan:
        """
        FR-010: Compare BUY vs WAIT.

        - Only buy if remaining runway >= LAND_MIN_RUNWAY.
        - Only buy if incremental value > cost.
        """
        cost = cfg.LAND_COST
        if cash < cost:
            return LandPlan(action="WAIT", cost=cost, reason="Insufficient cash.")

        if remaining_turns < cfg.LAND_MIN_RUNWAY:
            return LandPlan(
                action="WAIT", cost=cost,
                reason=f"Remaining turns ({remaining_turns}) < min runway ({cfg.LAND_MIN_RUNWAY})."
            )

        # Incremental value: one extra tile × avg value per crop turn × remaining turns
        incremental = avg_crop_value_per_turn * remaining_turns
        net = incremental - cost

        if net > 0 and empty_tiles == 0:
            return LandPlan(
                action="BUY", cost=cost,
                incremental_value=incremental, net_benefit=net,
                reason="Profitable expansion — no empty tiles remain.",
            )

        return LandPlan(
            action="WAIT", cost=cost,
            incremental_value=incremental, net_benefit=net,
            reason="Empty tiles still available or expansion unprofitable.",
        )

    def evaluate_labor(
        self,
        cash: float,
        remaining_turns: int,
        current_hire_index: int,
        pending_tasks: int,
        workers: int,
    ) -> LaborPlan:
        """
        FR-011: Compare HIRE vs WAIT.

        Marginal contribution ≈ (pending_tasks / workers) × avg_task_value × turns_per_day
        """
        hire_cost = cfg.HIRE_COSTS[min(current_hire_index, len(cfg.HIRE_COSTS) - 1)]

        if cash < hire_cost:
            return LaborPlan(action="WAIT", cost=hire_cost, reason="Insufficient cash.")

        if remaining_turns < cfg.TURNS_PER_DAY * 2:
            return LaborPlan(action="WAIT", cost=hire_cost,
                             reason="Too late in horizon to justify hiring.")

        if workers == 0:
            workers = 1
        tasks_per_worker = pending_tasks / workers
        avg_task_value = 5.0   # conservative estimate
        marginal = tasks_per_worker * avg_task_value * (remaining_turns / cfg.TURNS_PER_DAY)

        net = marginal - hire_cost
        if net > 0 and pending_tasks > workers * 3:
            return LaborPlan(
                action="HIRE", cost=hire_cost,
                marginal_contribution=marginal, net_benefit=net,
                reason="Profitable hire — high task backlog.",
            )

        return LaborPlan(
            action="WAIT", cost=hire_cost,
            marginal_contribution=marginal, net_benefit=net,
            reason="Hiring not justified by current task load.",
        )

    def bounded_replan(
        self,
        current_plan: Plan,
        candidate_plan: Plan,
    ) -> Plan:
        """
        FR-019: Accept candidate only if improvement is meaningful
        and the plan is not a repeated signature.
        Hard bound: MAX_REPLANS.
        """
        if self._replan_count >= cfg.MAX_REPLANS:
            current_plan.reason += " [replan bound reached]"
            return current_plan

        candidate_plan.compute_signature()
        if candidate_plan.signature in self._plan_signatures:
            current_plan.reason += " [oscillation detected — same plan signature]"
            return current_plan

        improvement = candidate_plan.expected_terminal_value - current_plan.expected_terminal_value
        min_improvement = 1.0  # $1 threshold to accept a new plan

        if improvement >= min_improvement:
            self._plan_signatures.add(candidate_plan.signature)
            self._replan_count += 1
            candidate_plan.replan_count = self._replan_count
            return candidate_plan

        current_plan.reason += f" [candidate improvement {improvement:.2f} below threshold]"
        return current_plan

    def reset_day(self) -> None:
        """Reset hire counter and replan counter at day boundary."""
        self._replan_count = 0
        self._plan_signatures = set()
