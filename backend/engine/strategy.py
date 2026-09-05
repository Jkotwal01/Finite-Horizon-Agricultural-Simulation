"""
engine/strategy.py — StrategyEngine (FR-010, FR-011, FR-016, FR-019 stub).

Land economics, labor economics, animal economics, and bounded counterfactual replanning.

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


@dataclass
class AnimalPlan:
    action: str = "WAIT"          # "BUILD" | "BUY" | "WAIT"
    kind: str = ""
    structure: str = ""
    cost: float = 0.0
    expected_revenue: float = 0.0
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

    def evaluate_animals(
        self,
        kind: str,
        cash: float,
        remaining_turns: int,
        has_structure: bool,
        current_animal_count: int,
    ) -> AnimalPlan:
        """
        FR-016: Compare acquiring an animal against waiting.

        Calculates:
        - Acquisition cost (structure if needed + animal cost)
        - Cumulative feed cost over remaining turns
        - Expected production revenue (discounted for late-horizon turns)
        """
        rules = cfg.ANIMAL_RULES.get(kind)
        if rules is None:
            return AnimalPlan(action="WAIT", reason=f"Unknown animal: {kind}.")

        # Must have enough turns for at least one production cycle
        if remaining_turns < rules["product_interval"] * 2:
            return AnimalPlan(
                action="WAIT", kind=kind,
                reason=f"Too late to recover investment in {kind} ({remaining_turns} turns left).",
            )

        structure_cost = 0.0 if has_structure else rules["structure_cost"]
        animal_cost = rules["cost"]
        total_acquisition_cost = structure_cost + animal_cost

        if cash < total_acquisition_cost:
            return AnimalPlan(
                action="WAIT", kind=kind, cost=total_acquisition_cost,
                reason=f"Insufficient cash (need ${total_acquisition_cost:.2f}, have ${cash:.2f}).",
            )

        # Expected production: number of full product intervals within remaining turns
        usable_turns = max(0, remaining_turns - rules["product_interval"])  # 1st interval = transit time
        production_cycles = usable_turns // rules["product_interval"]
        expected_revenue = production_cycles * rules["product_units"] * rules["sell_price"]

        # Cumulative feed cost over all remaining turns
        total_feed_cost = (remaining_turns / cfg.TURNS_PER_DAY) * rules["feed_cost_per_turn"]

        net = expected_revenue - total_acquisition_cost - total_feed_cost

        if net <= 0:
            return AnimalPlan(
                action="WAIT", kind=kind,
                cost=total_acquisition_cost,
                expected_revenue=expected_revenue,
                net_benefit=net,
                reason=f"Animal investment not profitable (net={net:.2f}).",
            )

        # Decide: need to build structure first, or can go straight to buy?
        if not has_structure:
            return AnimalPlan(
                action="BUILD", kind=kind, structure=rules["structure"],
                cost=structure_cost,
                expected_revenue=expected_revenue, net_benefit=net,
                reason=f"Must build {rules['structure']} before acquiring {kind}.",
            )

        return AnimalPlan(
            action="BUY", kind=kind, structure=rules["structure"],
            cost=animal_cost,
            expected_revenue=expected_revenue, net_benefit=net,
            reason=f"Profitable to acquire {kind} ({production_cycles} cycles, net=${net:.2f}).",
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
