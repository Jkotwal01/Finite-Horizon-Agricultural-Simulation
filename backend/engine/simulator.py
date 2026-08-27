"""
engine/simulator.py — Main simulation orchestrator.

Implements the end-to-end turn loop (WF-01):
Observe → Normalize → Memory → Mandatory Tasks → Forecasts →
Strategy → Scheduling → Validation → Execute → Advance → Telemetry.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import copy
import random
from models.state import CanonicalState, TimeState
from models.report import TerminalResult
from engine.observation import ObservationAdapter
from engine.state_manager import StateManager
from engine.crop_manager import CropManager
from engine.animal_manager import AnimalManager
from engine.warehouse import WarehouseManager
from engine.market import MarketEngine
from engine.forecast import ForecastEngine
from engine.scheduler import TaskScheduler
from engine.validator import ActionValidator
from engine.strategy import StrategyEngine
from engine.endgame import EndgameManager
from engine.telemetry import TelemetryEngine
import config as cfg


class Simulator:
    """
    Top-level simulation class. Owns all engines and drives the game loop.
    """

    def __init__(self) -> None:
        self.adapter = ObservationAdapter()
        self.state_mgr = StateManager()
        self.crop_mgr = CropManager()
        self.animal_mgr = AnimalManager()
        self.warehouse = WarehouseManager()
        self.market = MarketEngine()
        self.forecast_engine = ForecastEngine()
        self.scheduler = TaskScheduler()
        self.validator = ActionValidator()
        self.strategy = StrategyEngine()
        self.endgame_mgr = EndgameManager()
        self.telemetry = TelemetryEngine()

        self.current_state: CanonicalState | None = None
        self.current_turn: int = 0
        self.is_running: bool = False
        self.hire_index: int = 0   # reset daily
        self._last_day: int = -1

    # ── simulation control ────────────────────────────────────────────────────

    def start(self, initial_cash: float = cfg.INITIAL_CASH) -> dict:
        """Initialise the simulation with a fresh game state."""
        self.current_turn = 0
        self.is_running = True

        raw_obs = self._build_initial_observation(initial_cash)
        self.current_state = self.adapter.normalise(raw_obs)
        self.state_mgr.update(self.current_state)

        # Seed warehouse with starter supplies
        self.warehouse.add_to_shed("WHEAT_SEED", 5)
        self.warehouse.add_to_shed("TOMATO_SEED", 3)
        self.warehouse.add_to_shed("FERTILIZER", 5)
        self.warehouse.add_to_shed("FEED", 10)

        return {"status": "started", "turn": 0, "state": self.get_state_dict()}

    def step(self) -> dict:
        """Advance one turn. Returns the result of this turn."""
        if not self.is_running:
            return {"error": "Simulation not started. Call /start first."}
        if self.current_turn >= cfg.TOTAL_TURNS:
            return {"status": "finished", "terminal": self._compute_terminal().to_dict()}

        self.telemetry.start_turn(self.current_turn)

        try:
            result = self._run_turn()
        except Exception as e:
            self.telemetry.record_exception(self.current_turn, str(e))
            result = {"error": str(e), "turn": self.current_turn}

        self.current_turn += 1
        wealth = self.current_state.cash if self.current_state else 0.0
        elapsed = self.telemetry.end_turn(self.current_turn, wealth)
        result["elapsed_ms"] = round(elapsed, 2)
        result["turn"] = self.current_turn

        if self.current_turn >= cfg.TOTAL_TURNS:
            self.is_running = False
            result["terminal"] = self._compute_terminal().to_dict()

        return result

    def run_n_turns(self, n: int) -> dict:
        """Run up to n turns. Returns summary of all turns."""
        results = []
        for _ in range(min(n, cfg.TOTAL_TURNS - self.current_turn)):
            r = self.step()
            results.append(r)
            if not self.is_running:
                break
        return {
            "turns_run": len(results),
            "current_turn": self.current_turn,
            "is_finished": not self.is_running,
            "last_result": results[-1] if results else {},
        }

    # ── main turn logic ───────────────────────────────────────────────────────

    def _run_turn(self) -> dict:
        turn = self.current_turn
        time_state = self.state_mgr.get_time_state()

        # Reset daily counters
        if time_state.day != self._last_day:
            self._last_day = time_state.day
            self.hire_index = 0
            self.strategy.reset_day()

        # Reset market order counter for this turn
        self.market.reset_turn()

        # 1. Generate mandatory survival tasks
        tasks = []
        water_tasks = self.crop_mgr.generate_water_tasks(turn)
        feed_tasks = self.animal_mgr.generate_feed_tasks()
        tasks.extend(water_tasks)
        tasks.extend(feed_tasks)

        # 2. Advance crop and animal states
        crop_events = self.crop_mgr.advance_turn(turn)
        animal_events = self.animal_mgr.advance_turn(turn)

        for evt in crop_events:
            if evt["type"] == "DEAD":
                self.telemetry.record_crop_death(turn, evt["crop"])
        for evt in animal_events:
            if evt["type"] == "ANIMAL_DEAD":
                self.telemetry.record_animal_death(turn, evt["animal"])

        # 3. Warehouse forecast
        wh_forecast = self.warehouse.forecast(
            projected_inflow=len(self.crop_mgr.generate_harvest_tasks()),
            projected_outflow=0,
        )
        if wh_forecast.overflow_risk:
            self.telemetry.record_warehouse_overflow(turn)

        # 4. Production forecast
        prod_forecast = self.forecast_engine.full_forecast(
            crops=self.crop_mgr.get_all_crops(),
            animals=self.animal_mgr.get_all_animals(),
            current_turn=turn,
            horizon=cfg.TOTAL_TURNS,
        )

        # 5. Market / demand forecast
        demand_forecast = self.market.forecast_demand(
            current_day=time_state.day,
            remaining_turns=time_state.remaining_turns,
        )

        # 6. Economic tasks (harvest, sell, fertilize, plant)
        harvest_tasks = self.crop_mgr.generate_harvest_tasks()
        collect_tasks = self.animal_mgr.generate_collect_tasks()
        tasks.extend(harvest_tasks)
        tasks.extend(collect_tasks)

        # Fertilize if not endgame
        if not time_state.is_endgame:
            fertilizer_available = self.warehouse.get_seeds("FERTILIZER")
            fert_tasks = self.crop_mgr.generate_fertilizer_tasks(fertilizer_available)
            tasks.extend(fert_tasks)

        # 7. Endgame or normal sell planning
        inventory = self.warehouse.all_inventory()
        market_prices = {
            p: cfg.CROP_RULES[p]["base_sell_price"]
            for p in cfg.CROP_RULES
        }
        market_prices.update({
            cfg.ANIMAL_RULES[k]["product"]: cfg.ANIMAL_RULES[k]["sell_price"]
            for k in cfg.ANIMAL_RULES
        })

        if time_state.is_endgame:
            eg_plan = self.endgame_mgr.build_plan(
                crops=self.crop_mgr.get_all_crops(),
                inventory=inventory,
                market_prices=market_prices,
                current_turn=turn,
                remaining_turns=time_state.remaining_turns,
                cash=self.current_state.cash if self.current_state else 0,
            )
            for sell_a in eg_plan.sell_actions:
                tasks.append(self._sell_dict_to_task(sell_a, turn))
        else:
            market_plan = self.market.plan_sales(
                inventory=inventory,
                market_prices=market_prices,
                warehouse_emergency=wh_forecast.emergency_relief_needed,
            )
            for sell_a in market_plan.sell_actions:
                tasks.append(self._sell_dict_to_task(sell_a, turn))

        # 8. Schedule tasks to workers
        workers = self._get_workers()
        assignments = self.scheduler.schedule(tasks, workers)

        # 9. Convert assignments to action dicts and validate
        proposed_actions = [self._task_to_action(t) for t in assignments.assignments]
        state_snapshot = self._build_state_snapshot()
        validated = self.validator.validate_all(proposed_actions, state_snapshot)

        # 10. Log accepted / rejected
        for a in validated.accepted:
            self.telemetry.record_accepted_action(turn, a)
            self._apply_action(a)
        for r in validated.rejected:
            self.telemetry.record_invalid_action(turn, r["action"] if isinstance(r, dict) else r,
                                                  r.get("error", "") if isinstance(r, dict) else "")

        # 11. Auto-plant if there are empty tiles and we're not in endgame
        if not time_state.is_endgame:
            self._auto_plant(turn, time_state.remaining_turns)

        return {
            "status": "ok",
            "is_endgame": time_state.is_endgame,
            "remaining_turns": time_state.remaining_turns,
            "tasks_assigned": len(assignments.assignments),
            "tasks_unassigned": len(assignments.unassigned),
            "actions_accepted": len(validated.accepted),
            "actions_rejected": len(validated.rejected),
            "crop_events": crop_events,
            "animal_events": animal_events,
            "warehouse": wh_forecast.to_dict(),
            "production_forecast_value": prod_forecast.total_value,
            "state": self.get_state_dict(),
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    def _build_initial_observation(self, cash: float) -> dict:
        """Create the initial raw observation dict."""
        farms = []
        for r in range(cfg.BOARD_ROWS):
            for c in range(cfg.BOARD_COLS):
                farms.append({"row": r, "col": c, "status": "EMPTY", "locked": False})

        workers = [
            {"id": i, "row": 0, "col": 0, "carrying": {}}
            for i in range(cfg.INITIAL_WORKERS)
        ]

        return {
            "turn": 0,
            "cash": cash,
            "farms": farms,
            "market": {
                "WHEAT":      {"price": 8.0,  "inventory": 0, "sold_this_turn": 0},
                "TOMATO":     {"price": 10.0, "inventory": 0, "sold_this_turn": 0},
                "STRAWBERRY": {"price": 12.0, "inventory": 0, "sold_this_turn": 0},
                "MILK":       {"price": 15.0, "inventory": 0, "sold_this_turn": 0},
                "EGGS":       {"price": 5.0,  "inventory": 0, "sold_this_turn": 0},
            },
            "shops": [],
            "town": {"demand_events": []},
            "workers": workers,
            "structures": [],
            "shed_inventory": {},
            "animals": [],
        }

    def _get_workers(self) -> list[dict]:
        if self.current_state:
            return self.current_state.workers
        return [{"id": i, "row": 0, "col": 0} for i in range(cfg.INITIAL_WORKERS)]

    def _build_state_snapshot(self) -> dict:
        """Build snapshot dict for validator."""
        shed = self.warehouse.shed_snapshot()
        return {
            "cash": self.current_state.cash if self.current_state else 0,
            "shed_inventory": shed,
            "seeds": self.warehouse._seeds,
            "fertilizer": self.warehouse.get_seeds("FERTILIZER"),
            "feed": self.warehouse.get_seeds("FEED"),
            "market_orders_used": 0,
            "structures": [s["type"] for s in (self.current_state.structures if self.current_state else [])],
            "farms": self.current_state.farms if self.current_state else [],
        }

    def _task_to_action(self, task) -> dict:
        a = {
            "kind": task.kind,
            "task_id": task.task_id,
            "worker_id": task.worker_id,
            "target": task.target,
            "priority": task.priority,
        }
        a.update(task.metadata)
        return a

    def _sell_dict_to_task(self, sell_dict: dict, turn: int):
        from models.task import Task
        return Task(
            task_id=f"sell_{sell_dict['product']}_{turn}",
            kind="SELL",
            priority=sell_dict.get("priority", cfg.PRIORITY_SELL),
            value=sell_dict.get("expected_proceeds", 0),
            target=None,
            metadata=sell_dict,
        )

    def _apply_action(self, action: dict) -> None:
        """Update internal state after an accepted action."""
        kind = action.get("kind", "")

        if kind == "WATER":
            target = action.get("target", [])
            if target:
                self.crop_mgr.water_crop(target[0], target[1])

        elif kind == "FERTILIZE":
            target = action.get("target", [])
            if target:
                self.crop_mgr.fertilize_crop(target[0], target[1], self.current_turn)
            self.warehouse.remove_seed("FERTILIZER")

        elif kind == "HARVEST":
            target = action.get("target", [])
            if target:
                try:
                    product, units = self.crop_mgr.harvest_crop(target[0], target[1])
                    self.warehouse.add_to_shed(product, units)
                except ValueError:
                    pass

        elif kind == "COLLECT":
            animal_id = action.get("animal_id", "")
            if animal_id:
                product, units = self.animal_mgr.collect_product(animal_id)
                if units > 0:
                    self.warehouse.add_to_shed(product, units)

        elif kind == "FEED":
            animal_id = action.get("animal_id", "")
            if animal_id:
                self.animal_mgr.feed_animal(animal_id)
            self.warehouse.remove_seed("FEED")

        elif kind == "SELL":
            product = action.get("product", "")
            units = int(action.get("units", 0))
            base_price = {
                "WHEAT": 8.0, "TOMATO": 10.0, "STRAWBERRY": 12.0,
                "MILK": 15.0, "EGGS": 5.0,
            }.get(product, cfg.PRICE_FLOOR)
            proceeds = self.market.calculate_proceeds(product, units, base_price)
            self.warehouse.remove_from_shed(product, units)
            if self.current_state:
                self.current_state.cash += proceeds

    def _auto_plant(self, turn: int, remaining_turns: int) -> None:
        """Automatically plant seeds on empty tiles if viable."""
        if not self.current_state:
            return
        for tile in self.current_state.farms:
            if tile.get("status") != "EMPTY" or tile.get("locked"):
                continue
            for crop_type in ("TOMATO", "STRAWBERRY", "WHEAT"):
                seed_key = f"{crop_type}_SEED"
                if (self.warehouse.get_seeds(seed_key) > 0 and
                        self.crop_mgr.can_mature_before(crop_type, turn, turn + remaining_turns)):
                    try:
                        self.crop_mgr.plant(crop_type, tile["row"], tile["col"], turn)
                        self.warehouse.remove_seed(seed_key)
                        tile["status"] = "PLANTED"
                        break
                    except ValueError:
                        continue

    def _compute_terminal(self) -> TerminalResult:
        """FR-022: Compute deterministic terminal result."""
        cash = self.current_state.cash if self.current_state else 0.0
        inventory = self.warehouse.all_inventory()

        prices = {
            "WHEAT": 8.0, "TOMATO": 10.0, "STRAWBERRY": 12.0,
            "MILK": 15.0, "EGGS": 5.0,
        }

        inventory_value = sum(
            inventory.get(p, 0) * prices.get(p, 0)
            for p in prices
        )

        # Unrealizable: crops that can't mature before turn 720
        unrealizable = 0.0
        for crop in self.crop_mgr.get_all_crops():
            if not crop.is_dead and not crop.is_mature:
                rules = cfg.CROP_RULES[crop.crop]
                turns_left = rules["maturity_turns"] - crop.age
                if self.current_turn + turns_left > cfg.TOTAL_TURNS:
                    unrealizable += crop.yield_units * rules["base_sell_price"]

        result = TerminalResult(
            turn=self.current_turn,
            cash=round(cash, 2),
            inventory_value=round(inventory_value, 2),
            asset_value=0.0,
            penalties=0.0,
            unrealizable_production=round(unrealizable, 2),
            exceptions=self.telemetry.report.exceptions,
            invalid_actions=self.telemetry.report.invalid_actions,
        )
        result.compute()
        self.telemetry.finalise(result)
        return result

    def get_state_dict(self) -> dict:
        """Return a serialisable snapshot of the current simulation state."""
        if not self.current_state:
            return {}
        time_state = self.state_mgr.get_time_state() if self.state_mgr.time_state else None
        return {
            "turn": self.current_turn,
            "day": time_state.day if time_state else 0,
            "hour": time_state.hour if time_state else 0,
            "remaining_turns": time_state.remaining_turns if time_state else cfg.TOTAL_TURNS,
            "is_endgame": time_state.is_endgame if time_state else False,
            "cash": round(self.current_state.cash, 2),
            "farms": self.current_state.farms,
            "workers": self.current_state.workers,
            "shed_inventory": self.warehouse.shed_snapshot(),
            "seeds": dict(self.warehouse._seeds),
            "crops": [c.to_dict() for c in self.crop_mgr.get_all_crops()],
            "animals": [a.to_dict() for a in self.animal_mgr.get_all_animals()],
            "warehouse_total": self.warehouse.total_non_seed_units(),
            "warehouse_capacity": cfg.SHED_CAPACITY,
        }
