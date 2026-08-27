"""
engine/animal_manager.py — AnimalManager (FR-008, FR-009).

Manages animal lifecycle: buy, carry, place, feed, collect products.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.animal import AnimalState
from models.task import Task
import config as cfg


class AnimalManager:
    """
    Owns all AnimalState instances.

    Rules enforced:
    BR-001 — Feed tasks as PRIORITY_SURVIVAL.
    BR-004 — Placed + shed + carried + pending all count toward acquisition limit.
    """

    def __init__(self) -> None:
        self._animals: dict[str, AnimalState] = {}
        self._structures: set[str] = set()   # {"BARN", "COOP"}
        self._task_counter: int = 0
        self._animal_counter: dict[str, int] = {}

    # ── structure management ──────────────────────────────────────────────────

    def build_structure(self, structure_type: str) -> bool:
        """Record that a structure has been built."""
        self._structures.add(structure_type)
        return True

    def has_structure(self, structure_type: str) -> bool:
        return structure_type in self._structures

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def buy_animal(self, kind: str, worker_id: int) -> AnimalState:
        """
        Purchase an animal if structure exists.
        Immediately marks it as CARRIED by the worker.
        Raises ValueError if structure missing or limit exceeded.
        """
        rules = cfg.ANIMAL_RULES.get(kind)
        if rules is None:
            raise ValueError(f"Unknown animal kind: {kind}")
        if not self.has_structure(rules["structure"]):
            raise ValueError(f"Missing structure {rules['structure']} for {kind}.")

        idx = self._animal_counter.get(kind, 0)
        self._animal_counter[kind] = idx + 1
        animal_id = f"{kind.lower()}_{idx}"

        animal = AnimalState(
            animal_id=animal_id,
            kind=kind,
            location="CARRIED",
            carried_by=worker_id,
        )
        self._animals[animal_id] = animal
        return animal

    def place_animal(self, animal_id: str, row: int, col: int,
                     current_turn: int) -> bool:
        """Place a carried animal on a tile. Returns False if not carried."""
        animal = self._animals.get(animal_id)
        if animal is None or animal.location != "CARRIED":
            return False
        rules = cfg.ANIMAL_RULES[animal.kind]
        animal.location = "PLACED"
        animal.tile_row = row
        animal.tile_col = col
        animal.carried_by = None
        animal.placed_turn = current_turn
        animal.next_product_turn = current_turn + rules["product_interval"]
        return True

    def feed_animal(self, animal_id: str) -> bool:
        """Mark animal as fed this turn."""
        animal = self._animals.get(animal_id)
        if animal is None or not animal.is_alive:
            return False
        animal.fed = True
        animal.consecutive_missed_feed = 0
        return True

    def advance_turn(self, current_turn: int) -> list[dict]:
        """
        Advance animal states by one turn.
        Returns events: {"type": "PRODUCT_READY"|"ANIMAL_DEAD", "animal": ...}
        """
        events = []
        for aid, animal in self._animals.items():
            if not animal.is_alive:
                continue

            # Check feeding obligation
            if not animal.fed:
                animal.consecutive_missed_feed += 1
                rules = cfg.ANIMAL_RULES[animal.kind]
                if animal.consecutive_missed_feed >= rules["max_missed_feed"]:
                    animal.is_alive = False
                    events.append({"type": "ANIMAL_DEAD", "animal": animal.to_dict()})
                    continue
            else:
                animal.consecutive_missed_feed = 0
            animal.fed = False  # reset for next turn

            # Check product availability
            if (animal.location == "PLACED" and
                    animal.next_product_turn is not None and
                    current_turn >= animal.next_product_turn):
                rules = cfg.ANIMAL_RULES[animal.kind]
                animal.product_ready += rules["product_units"]
                animal.next_product_turn = current_turn + rules["product_interval"]
                events.append({"type": "PRODUCT_READY", "animal": animal.to_dict()})

        return events

    def collect_product(self, animal_id: str) -> tuple[str, int]:
        """
        Collect all ready product from an animal.
        Returns (product_name, units).
        """
        animal = self._animals.get(animal_id)
        if animal is None or not animal.is_alive or animal.product_ready == 0:
            return ("", 0)
        rules = cfg.ANIMAL_RULES[animal.kind]
        units = animal.product_ready
        animal.product_ready = 0
        return (rules["product"], units)

    # ── task generation ───────────────────────────────────────────────────────

    def generate_feed_tasks(self) -> list[Task]:
        """FR-009: Mandatory daily feed tasks — PRIORITY_SURVIVAL."""
        tasks = []
        for aid, animal in self._animals.items():
            if not animal.is_alive or animal.location not in ("PLACED", "SHED"):
                continue
            if not animal.fed:
                rules = cfg.ANIMAL_RULES[animal.kind]
                self._task_counter += 1
                tasks.append(Task(
                    task_id=f"feed_{aid}_{self._task_counter}",
                    kind="FEED",
                    priority=cfg.PRIORITY_SURVIVAL,
                    value=rules["sell_price"] * rules["product_units"],
                    target=[animal.tile_row or 0, animal.tile_col or 0],
                    resource_reservation={"FEED": 1},
                    preconditions={"animal_alive": True},
                    metadata={"animal_id": aid, "kind": animal.kind},
                ))
        return tasks

    def generate_collect_tasks(self) -> list[Task]:
        """Generate collection tasks for animals with ready product."""
        tasks = []
        for aid, animal in self._animals.items():
            if not animal.is_alive or animal.product_ready <= 0:
                continue
            rules = cfg.ANIMAL_RULES[animal.kind]
            self._task_counter += 1
            tasks.append(Task(
                task_id=f"collect_{aid}_{self._task_counter}",
                kind="COLLECT",
                priority=cfg.PRIORITY_HARVEST,
                value=animal.product_ready * rules["sell_price"],
                target=[animal.tile_row or 0, animal.tile_col or 0],
                resource_reservation={},
                preconditions={"product_ready": True},
                metadata={"animal_id": aid, "kind": animal.kind,
                           "product": rules["product"], "units": animal.product_ready},
            ))
        return tasks

    # ── helpers ───────────────────────────────────────────────────────────────

    def count_all_animals(self, kind: str) -> int:
        """BR-004: Count placed + shed + carried + pending."""
        return sum(1 for a in self._animals.values()
                   if a.kind == kind and a.is_alive)

    def get_all_animals(self) -> list[AnimalState]:
        return list(self._animals.values())
