"""
test_animal_logistics.py — FR-008, FR-009, FR-016 Animal Logistics Tests

Covers the full animal acquisition pipeline:
  strategy.evaluate_animals() → BUILD_STRUCTURE → BUY_ANIMAL → PLACE_ANIMAL
  → feeding → product collection
"""
from backend.engine.strategy import StrategyEngine, AnimalPlan
from backend.engine.animal_manager import AnimalManager
from backend.engine.validator import ActionValidator
import backend.config as cfg


class TestAnimalEconomics:
    """FR-016: evaluate_animals() ROI calculations."""

    def setup_method(self):
        self.strategy = StrategyEngine()

    def test_cow_profitable_early(self):
        """Buying a COW early (300 turns left) should be profitable."""
        plan = self.strategy.evaluate_animals(
            kind="COW", cash=1000.0, remaining_turns=300,
            has_structure=True, current_animal_count=0,
        )
        assert plan.action == "BUY"
        assert plan.net_benefit > 0

    def test_cow_needs_structure_first(self):
        """If BARN not built, action should be BUILD not BUY."""
        # Use enough remaining turns so total revenue > structure + animal + feed costs
        plan = self.strategy.evaluate_animals(
            kind="COW", cash=2000.0, remaining_turns=600,
            has_structure=False, current_animal_count=0,
        )
        assert plan.action == "BUILD"
        assert plan.structure == "BARN"

    def test_cow_too_late(self):
        """Should WAIT if remaining_turns < 2 product intervals."""
        intervals = cfg.ANIMAL_RULES["COW"]["product_interval"]
        plan = self.strategy.evaluate_animals(
            kind="COW", cash=1000.0,
            remaining_turns=intervals,  # only 1 interval left
            has_structure=True, current_animal_count=0,
        )
        assert plan.action == "WAIT"
        assert "late" in plan.reason.lower() or "turns" in plan.reason.lower()

    def test_cow_insufficient_cash(self):
        """Should WAIT if not enough cash for structure + animal."""
        plan = self.strategy.evaluate_animals(
            kind="COW", cash=10.0, remaining_turns=400,
            has_structure=False, current_animal_count=0,
        )
        assert plan.action == "WAIT"
        assert "cash" in plan.reason.lower()

    def test_chicken_profitable_early(self):
        """Buying a CHICKEN early should be profitable (cheap, frequent eggs)."""
        plan = self.strategy.evaluate_animals(
            kind="CHICKEN", cash=500.0, remaining_turns=300,
            has_structure=True, current_animal_count=0,
        )
        assert plan.action == "BUY"
        assert plan.net_benefit > 0

    def test_unknown_animal_returns_wait(self):
        plan = self.strategy.evaluate_animals(
            kind="DRAGON", cash=1000.0, remaining_turns=400,
            has_structure=False, current_animal_count=0,
        )
        assert plan.action == "WAIT"


class TestAnimalManagerTasks:
    """FR-008: Task generation from AnimalManager."""

    def setup_method(self):
        self.mgr = AnimalManager()

    def test_build_structure_task_generated_when_not_built(self):
        tasks = self.mgr.generate_build_structure_tasks("BARN", 150.0)
        assert len(tasks) == 1
        assert tasks[0].kind == "BUILD_STRUCTURE"
        assert tasks[0].metadata["structure_type"] == "BARN"

    def test_build_structure_task_skipped_when_already_built(self):
        self.mgr.build_structure("BARN")
        tasks = self.mgr.generate_build_structure_tasks("BARN", 150.0)
        assert tasks == []

    def test_buy_animal_task_requires_structure(self):
        """Should return empty if structure not built."""
        tasks = self.mgr.generate_buy_animal_tasks("COW")
        assert tasks == []

    def test_buy_animal_task_generated_after_structure(self):
        self.mgr.build_structure("BARN")
        tasks = self.mgr.generate_buy_animal_tasks("COW")
        assert len(tasks) == 1
        assert tasks[0].kind == "BUY_ANIMAL"
        assert tasks[0].metadata["kind_animal"] == "COW"

    def test_place_animal_task_for_carried_animal(self):
        self.mgr.build_structure("BARN")
        self.mgr.buy_animal("COW", worker_id=0)  # starts as CARRIED
        tasks = self.mgr.generate_place_animal_tasks([(2, 3), (3, 3)])
        assert len(tasks) == 1
        assert tasks[0].kind == "PLACE_ANIMAL"
        assert tasks[0].target == [2, 3]

    def test_no_place_tasks_if_no_carried_animals(self):
        tasks = self.mgr.generate_place_animal_tasks([(0, 0)])
        assert tasks == []


class TestAnimalValidation:
    """Validator checks for BUILD_STRUCTURE and BUY_ANIMAL."""

    def setup_method(self):
        self.validator = ActionValidator()

    def _snapshot(self, cash=1000.0, structures=None):
        return {
            "cash": cash, "shed_inventory": {}, "seeds": {},
            "fertilizer": 0, "feed": 10,
            "market_orders_used": 0,
            "structures": structures or [],
            "farms": {},
        }

    def test_build_structure_accepted_with_enough_cash(self):
        snap = self._snapshot(cash=1000.0)
        result = self.validator.validate_all(
            [{"kind": "BUILD_STRUCTURE", "structure_type": "BARN"}], snap
        )
        assert len(result.accepted) == 1

    def test_build_structure_rejected_insufficient_cash(self):
        snap = self._snapshot(cash=10.0)
        result = self.validator.validate_all(
            [{"kind": "BUILD_STRUCTURE", "structure_type": "BARN"}], snap
        )
        assert len(result.rejected) == 1

    def test_build_structure_rejected_if_already_built(self):
        snap = self._snapshot(cash=1000.0, structures=["BARN"])
        result = self.validator.validate_all(
            [{"kind": "BUILD_STRUCTURE", "structure_type": "BARN"}], snap
        )
        assert len(result.rejected) == 1

    def test_buy_animal_rejected_without_structure(self):
        snap = self._snapshot(cash=1000.0, structures=[])
        result = self.validator.validate_all(
            [{"kind": "BUY_ANIMAL", "kind_animal": "COW"}], snap
        )
        assert len(result.rejected) == 1

    def test_buy_animal_accepted_with_structure(self):
        snap = self._snapshot(cash=1000.0, structures=["BARN"])
        result = self.validator.validate_all(
            [{"kind": "BUY_ANIMAL", "kind_animal": "COW"}], snap
        )
        assert len(result.accepted) == 1

    def test_sequential_build_then_buy_in_same_turn(self):
        """Build BARN and immediately buy COW in same validation batch (BR-012)."""
        snap = self._snapshot(cash=1000.0, structures=[])
        actions = [
            {"kind": "BUILD_STRUCTURE", "structure_type": "BARN"},
            {"kind": "BUY_ANIMAL", "kind_animal": "COW"},
        ]
        result = self.validator.validate_all(actions, snap)
        # Both should be accepted — the sim state after BUILD includes BARN
        assert len(result.accepted) == 2, (
            f"Expected 2 accepted, got {len(result.accepted)}. "
            f"Rejected: {[r for r in result.validation_log if not r.accepted]}"
        )

    def test_place_animal_rejected_without_animal_id(self):
        snap = self._snapshot(cash=1000.0)
        result = self.validator.validate_all(
            [{"kind": "PLACE_ANIMAL", "target": [0, 0]}], snap
        )
        assert len(result.rejected) == 1

    def test_place_animal_rejected_without_target(self):
        snap = self._snapshot(cash=1000.0)
        result = self.validator.validate_all(
            [{"kind": "PLACE_ANIMAL", "animal_id": "cow_0"}], snap
        )
        assert len(result.rejected) == 1


class TestAnimalSimulatorIntegration:
    """End-to-end: BUILD → BUY → PLACE → FEED → COLLECT lifecycle in Simulator."""

    def test_build_structure_action_reduces_cash_and_registers_structure(self):
        from backend.engine.simulator import Simulator
        sim = Simulator()
        sim.start(initial_cash=2000.0)

        initial_cash = sim.current_state.cash
        sim._apply_action({"kind": "BUILD_STRUCTURE", "structure_type": "BARN"})

        barn_cost = cfg.ANIMAL_RULES["COW"]["structure_cost"]
        assert sim.current_state.cash == initial_cash - barn_cost
        assert sim.animal_mgr.has_structure("BARN")

    def test_buy_animal_after_structure_creates_carried_animal(self):
        from backend.engine.simulator import Simulator
        sim = Simulator()
        sim.start(initial_cash=2000.0)
        sim._apply_action({"kind": "BUILD_STRUCTURE", "structure_type": "BARN"})

        cow_cost = cfg.ANIMAL_RULES["COW"]["cost"]
        cash_before_buy = sim.current_state.cash
        sim._apply_action({"kind": "BUY_ANIMAL", "kind_animal": "COW"})

        assert sim.current_state.cash == cash_before_buy - cow_cost
        animals = sim.animal_mgr.get_all_animals()
        assert len(animals) == 1
        assert animals[0].kind == "COW"
        assert animals[0].location == "CARRIED"

    def test_place_animal_transitions_to_placed(self):
        from backend.engine.simulator import Simulator
        sim = Simulator()
        sim.start(initial_cash=2000.0)
        sim._apply_action({"kind": "BUILD_STRUCTURE", "structure_type": "BARN"})
        sim._apply_action({"kind": "BUY_ANIMAL", "kind_animal": "COW"})

        cow = sim.animal_mgr.get_all_animals()[0]
        sim._apply_action({
            "kind": "PLACE_ANIMAL",
            "animal_id": cow.animal_id,
            "target": [0, 0],
        })

        assert cow.location == "PLACED"
        assert cow.tile_row == 0
        assert cow.tile_col == 0

    def test_full_cow_lifecycle(self):
        """Build BARN → Buy COW → Place → Feed → advance → collect MILK."""
        from backend.engine.simulator import Simulator
        sim = Simulator()
        sim.start(initial_cash=2000.0)

        # Acquire
        sim._apply_action({"kind": "BUILD_STRUCTURE", "structure_type": "BARN"})
        sim._apply_action({"kind": "BUY_ANIMAL", "kind_animal": "COW"})
        cow = sim.animal_mgr.get_all_animals()[0]
        sim._apply_action({"kind": "PLACE_ANIMAL", "animal_id": cow.animal_id, "target": [0, 0]})

        # Add feed and advance enough turns for one milk cycle (24 turns)
        # We need current_turn to *reach* next_product_turn (which is placed_turn + interval)
        interval = cfg.ANIMAL_RULES["COW"]["product_interval"]
        for i in range(interval + 1):  # +1 ensures the >= condition is met
            sim.animal_mgr.feed_animal(cow.animal_id)
            sim.animal_mgr.advance_turn(sim.current_turn)
            sim.current_turn += 1

        # Cow should have product ready
        assert cow.product_ready > 0

        # Collect milk into warehouse
        product, units = sim.animal_mgr.collect_product(cow.animal_id)
        sim.warehouse.add_to_shed(product, units)
        assert product == "MILK"
        assert units == cfg.ANIMAL_RULES["COW"]["product_units"]
        assert sim.warehouse.shed_snapshot().get("MILK", 0) >= units
