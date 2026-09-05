from backend.engine.strategy import StrategyEngine
import backend.config as cfg

class TestStrategyEngine:

    def setup_method(self):
        self.strategy = StrategyEngine()

    def test_evaluate_land_profitable(self):
        """Should buy land if there are no empty tiles and remaining turns > minimum."""
        cash = 500.0
        remaining = 150
        empty_tiles = 0
        
        plan = self.strategy.evaluate_land(cash, remaining, empty_tiles)
        assert plan.action == "BUY"
        assert plan.cost == cfg.LAND_COST
        assert plan.incremental_value > plan.cost
        assert plan.net_benefit > 0

    def test_evaluate_land_unprofitable(self):
        """Should WAIT if remaining turns is below the minimum runway to recover cost."""
        cash = 500.0
        remaining = 50  # Less than LAND_MIN_RUNWAY (96)
        empty_tiles = 0
        
        plan = self.strategy.evaluate_land(cash, remaining, empty_tiles)
        assert plan.action == "WAIT"
        assert plan.net_benefit <= 0 or "runway" in plan.reason.lower()

    def test_evaluate_land_insufficient_cash(self):
        """Should WAIT if cash is below land cost."""
        cash = 50.0
        remaining = 200
        empty_tiles = 0
        
        plan = self.strategy.evaluate_land(cash, remaining, empty_tiles)
        assert plan.action == "WAIT"
        assert "cash" in plan.reason.lower()

    def test_evaluate_labor_profitable(self):
        """Should HIRE if pending tasks severely outnumber workers and cash is sufficient."""
        cash = 500.0
        remaining = 150
        hire_index = 0
        pending_tasks = 10
        workers = 1
        
        plan = self.strategy.evaluate_labor(cash, remaining, hire_index, pending_tasks, workers)
        assert plan.action == "HIRE"
        assert plan.cost == cfg.HIRE_COSTS[0]
        assert plan.net_benefit > 0

    def test_evaluate_labor_unprofitable(self):
        """Should WAIT if there are not enough pending tasks to justify hiring."""
        cash = 500.0
        remaining = 150
        hire_index = 0
        pending_tasks = 2
        workers = 2
        
        plan = self.strategy.evaluate_labor(cash, remaining, hire_index, pending_tasks, workers)
        assert plan.action == "WAIT"

    def test_evaluate_labor_late_horizon(self):
        """Should WAIT if it's too late in the game (e.g. last 2 days)."""
        cash = 500.0
        remaining = cfg.TURNS_PER_DAY * 1  # Less than 2 days
        hire_index = 0
        pending_tasks = 10
        workers = 1
        
        plan = self.strategy.evaluate_labor(cash, remaining, hire_index, pending_tasks, workers)
        assert plan.action == "WAIT"
        assert "late" in plan.reason.lower()

    def test_apply_buy_land_action(self):
        """Integration test for BUY_LAND action execution in Simulator."""
        from backend.engine.simulator import Simulator
        sim = Simulator()
        sim.start(initial_cash=500.0)
        
        initial_farms = len(sim.current_state.farms)
        initial_cash = sim.current_state.cash
        
        action = {"kind": "BUY_LAND"}
        sim._apply_action(action)
        
        assert sim.current_state.cash == initial_cash - cfg.LAND_COST
        assert len(sim.current_state.farms) == initial_farms + 1
        assert sim.current_state.farms[-1]["status"] == "EMPTY"

    def test_apply_hire_action(self):
        """Integration test for HIRE action execution in Simulator."""
        from backend.engine.simulator import Simulator
        sim = Simulator()
        sim.start(initial_cash=500.0)
        
        initial_workers = len(sim.current_state.workers)
        initial_cash = sim.current_state.cash
        
        action = {"kind": "HIRE", "hire_index": 0}
        sim._apply_action(action)
        
        assert sim.current_state.cash == initial_cash - cfg.HIRE_COSTS[0]
        assert len(sim.current_state.workers) == initial_workers + 1
        assert sim.hire_index == 1
