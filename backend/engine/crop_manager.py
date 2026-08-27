"""
engine/crop_manager.py — CropManager (FR-005, FR-006, FR-007).

Manages crop lifecycle: planting, watering, fertilizing, harvesting.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.crop import CropState
from models.task import Task
import config as cfg


class CropManager:
    """
    Owns all active CropState instances and drives the crop lifecycle.

    Rules enforced:
    BR-001 Survival priority — watering tasks created as PRIORITY_SURVIVAL.
    BR-011 Endgame viability — no planting if crop cannot mature before horizon.
    """

    def __init__(self) -> None:
        self._crops: dict[tuple[int, int], CropState] = {}  # tile → crop
        self._task_counter: int = 0

    # ── public interface ──────────────────────────────────────────────────────

    def plant(self, crop_type: str, row: int, col: int, current_turn: int) -> CropState:
        """Plant a crop. Raises if tile is occupied or crop type unknown."""
        if crop_type not in cfg.CROP_RULES:
            raise ValueError(f"Unknown crop type: {crop_type}")
        if (row, col) in self._crops:
            raise ValueError(f"Tile ({row},{col}) already has a crop.")
        rules = cfg.CROP_RULES[crop_type]
        state = CropState(
            crop=crop_type,
            tile_row=row,
            tile_col=col,
            planted_turn=current_turn,
            yield_units=rules["yield_units"],
            base_yield=rules["yield_units"],
            next_production_turn=current_turn + rules["maturity_turns"],
        )
        self._crops[(row, col)] = state
        return state

    def advance_turn(self, current_turn: int) -> list[dict]:
        """
        Advance all crops by one turn.
        Returns a list of events: {"type": "MATURED"|"DEAD"|"PRODUCED", "crop": crop_dict}
        """
        events = []
        dead_tiles = []
        for tile, crop in self._crops.items():
            if crop.is_dead:
                continue
            crop.age += 1
            rules = cfg.CROP_RULES[crop.crop]

            # Check watering obligation (water_every = 1 means every turn)
            # Watering is applied externally; here we check if it was missed
            # (water_status is set to "WATERED" when WATER action executes)
            if crop.water_status != "WATERED":
                crop.consecutive_missed_water += 1
                crop.water_status = f"MISSED_{crop.consecutive_missed_water}"
                if crop.consecutive_missed_water >= rules["max_missed_water"]:
                    crop.is_dead = True
                    crop.water_status = "DEAD"
                    dead_tiles.append(tile)
                    events.append({"type": "DEAD", "crop": crop.to_dict()})
                    continue
            else:
                crop.consecutive_missed_water = 0
                crop.water_status = "PENDING"   # reset for next turn

            # Check maturity
            if not crop.is_mature and current_turn >= crop.next_production_turn:
                crop.is_mature = True
                events.append({"type": "MATURED", "crop": crop.to_dict()})

            # Ongoing production
            if crop.is_mature and not rules["one_time"]:
                if (crop.next_production_turn is not None and
                        current_turn >= crop.next_production_turn):
                    events.append({"type": "PRODUCED", "crop": crop.to_dict()})
                    crop.harvest_count += 1
                    crop.next_production_turn = current_turn + rules["ongoing_interval"]

        for tile in dead_tiles:
            pass  # keep dead crops in dict for telemetry; cleared on harvest

        return events

    def water_crop(self, row: int, col: int) -> bool:
        """Mark a crop as watered this turn. Returns False if no crop exists."""
        crop = self._crops.get((row, col))
        if crop is None or crop.is_dead:
            return False
        crop.water_status = "WATERED"
        crop.consecutive_missed_water = 0
        return True

    def fertilize_crop(self, row: int, col: int, current_turn: int) -> bool:
        """Apply fertilizer if crop is within the eligible window."""
        crop = self._crops.get((row, col))
        if crop is None or crop.is_dead or crop.fertilized:
            return False
        rules = cfg.CROP_RULES[crop.crop]
        w_start, w_end = rules["fertilizer_window"]
        if w_start <= crop.age <= w_end:
            crop.fertilized = True
            crop.yield_units = crop.base_yield + rules["fertilizer_bonus"]
            return True
        return False

    def harvest_crop(self, row: int, col: int) -> tuple[str, int]:
        """
        Harvest a mature crop.
        Returns (product_name, units). Removes one-time crops from the board.
        """
        crop = self._crops.get((row, col))
        if crop is None or not crop.is_mature:
            raise ValueError(f"No mature crop at ({row},{col}).")
        rules = cfg.CROP_RULES[crop.crop]
        units = crop.yield_units
        product = crop.crop  # product name = crop name for simplicity

        if rules["one_time"]:
            del self._crops[(row, col)]
        else:
            crop.harvest_count += 1
            # next production already set in advance_turn

        return product, units

    def generate_water_tasks(self, current_turn: int) -> list[Task]:
        """FR-006: Mandatory watering tasks for all crops needing water."""
        tasks = []
        for tile, crop in self._crops.items():
            if crop.is_dead:
                continue
            if crop.water_status in ("PENDING", f"MISSED_1", f"MISSED_2"):
                self._task_counter += 1
                tasks.append(Task(
                    task_id=f"water_{tile[0]}_{tile[1]}_{self._task_counter}",
                    kind="WATER",
                    priority=cfg.PRIORITY_SURVIVAL,
                    value=self._crop_value(crop),
                    target=list(tile),
                    resource_reservation={},
                    preconditions={"tile_has_crop": True},
                    metadata={"crop": crop.crop, "age": crop.age},
                ))
        return tasks

    def generate_fertilizer_tasks(self, fertilizer_available: int) -> list[Task]:
        """FR-007: Fertilizer tasks, reserving one unit per eligible crop."""
        tasks = []
        reserved = 0
        for tile, crop in self._crops.items():
            if crop.is_dead or crop.fertilized:
                continue
            if reserved >= fertilizer_available:
                break
            rules = cfg.CROP_RULES[crop.crop]
            w_start, w_end = rules["fertilizer_window"]
            if w_start <= crop.age <= w_end:
                reserved += 1
                self._task_counter += 1
                tasks.append(Task(
                    task_id=f"fert_{tile[0]}_{tile[1]}_{self._task_counter}",
                    kind="FERTILIZE",
                    priority=cfg.PRIORITY_FERTILIZE,
                    value=rules["fertilizer_bonus"] * rules["base_sell_price"],
                    target=list(tile),
                    resource_reservation={"FERTILIZER": 1},
                    preconditions={"crop_in_window": True},
                    metadata={"crop": crop.crop, "age": crop.age},
                ))
        return tasks

    def generate_harvest_tasks(self) -> list[Task]:
        """Generate tasks for all mature/ready crops."""
        tasks = []
        for tile, crop in self._crops.items():
            if crop.is_dead:
                continue
            if crop.is_mature:
                self._task_counter += 1
                rules = cfg.CROP_RULES[crop.crop]
                tasks.append(Task(
                    task_id=f"harvest_{tile[0]}_{tile[1]}_{self._task_counter}",
                    kind="HARVEST",
                    priority=cfg.PRIORITY_HARVEST,
                    value=crop.yield_units * rules["base_sell_price"],
                    target=list(tile),
                    resource_reservation={},
                    preconditions={"crop_mature": True},
                    metadata={"crop": crop.crop, "yield_units": crop.yield_units},
                ))
        return tasks

    def can_mature_before(self, crop_type: str, current_turn: int,
                          horizon: int) -> bool:
        """BR-011: Returns True only if the crop can complete one harvest before horizon."""
        if crop_type not in cfg.CROP_RULES:
            return False
        maturity = cfg.CROP_RULES[crop_type]["maturity_turns"]
        return (current_turn + maturity) <= horizon

    def get_all_crops(self) -> list[CropState]:
        return list(self._crops.values())

    def remove_dead_crops(self) -> int:
        """Remove dead crops from the board. Returns count removed."""
        dead = [t for t, c in self._crops.items() if c.is_dead]
        for t in dead:
            del self._crops[t]
        return len(dead)

    # ── private ───────────────────────────────────────────────────────────────

    def _crop_value(self, crop: CropState) -> float:
        rules = cfg.CROP_RULES[crop.crop]
        return crop.yield_units * rules["base_sell_price"]
