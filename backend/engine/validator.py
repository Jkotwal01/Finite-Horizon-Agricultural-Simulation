"""
engine/validator.py — ActionValidator (FR-018).

Sequential action validation: each action is validated against the state
AFTER all preceding accepted actions in the same turn.

Rules:
- BR-012: Validation uses state resulting from preceding actions.
- Checks: syntax, target legality, resource availability, capacity, prerequisites.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
from models.task import Task
import config as cfg


@dataclass
class ValidationResult:
    action: dict
    accepted: bool
    error: str = ""


@dataclass
class ValidatedActions:
    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    validation_log: list[ValidationResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected),
            "accepted": self.accepted,
            "rejected": [
                {"action": r.action, "error": r.error}
                for r in self.validation_log if not r.accepted
            ],
        }


class ActionValidator:
    """
    Validates a list of proposed actions sequentially.

    Simulated state is updated after each accepted action so subsequent
    actions see the correct resource levels.
    """

    def validate_all(
        self,
        actions: list[dict],
        state_snapshot: dict,
    ) -> ValidatedActions:
        """
        Validate each action in order using a mutable simulated state.

        state_snapshot keys:
            cash, shed_inventory, workers, structures, farms, market_orders_used
        """
        # Deep-copy mutable state to avoid corrupting real state
        sim = {
            "cash": float(state_snapshot.get("cash", 0)),
            "shed": dict(state_snapshot.get("shed_inventory", {})),
            "seeds": dict(state_snapshot.get("seeds", {})),
            "fertilizer": int(state_snapshot.get("fertilizer", 0)),
            "feed": int(state_snapshot.get("feed", 0)),
            "market_orders_used": int(state_snapshot.get("market_orders_used", 0)),
            "worker_carrying": dict(state_snapshot.get("worker_carrying", {})),
            "structures": list(state_snapshot.get("structures", [])),
            "farms": {
                (t["row"], t["col"]): t
                for t in state_snapshot.get("farms", [])
            },
        }

        result = ValidatedActions()

        for action in actions:
            ok, err = self._validate_one(action, sim)
            vr = ValidationResult(action=action, accepted=ok, error=err)
            result.validation_log.append(vr)

            if ok:
                result.accepted.append(action)
                self._apply(action, sim)   # update simulated state
            else:
                result.rejected.append(action)

        return result

    # ── per-action validation ─────────────────────────────────────────────────

    def _validate_one(self, action: dict, sim: dict) -> tuple[bool, str]:
        kind = action.get("kind", "")

        validators = {
            "SELL":             self._validate_sell,
            "WATER":            self._validate_water,
            "HARVEST":          self._validate_harvest,
            "PLANT":            self._validate_plant,
            "FERTILIZE":        self._validate_fertilize,
            "FEED":             self._validate_feed,
            "BUY_ANIMAL":       self._validate_buy_animal,
            "COLLECT":          self._validate_collect,
            "BUY_LAND":         self._validate_buy_land,
            "HIRE":             self._validate_hire,
            "BUILD_STRUCTURE":  self._validate_build_structure,
            "PLACE_ANIMAL":     self._validate_place_animal,
        }

        validator = validators.get(kind)
        if validator is None:
            return False, f"Unknown action kind: {kind}"
        return validator(action, sim)

    def _validate_sell(self, a: dict, sim: dict) -> tuple[bool, str]:
        if sim["market_orders_used"] >= cfg.MAX_ORDERS:
            return False, f"Max {cfg.MAX_ORDERS} market orders reached."
        product = a.get("product", "")
        if product.endswith("_SEED") or product == "FERTILIZER":
            return False, f"Cannot sell {product}."
        units = int(a.get("units", 0))
        if sim["shed"].get(product, 0) < units:
            return False, f"Insufficient {product} in shed ({sim['shed'].get(product,0)} < {units})."
        return True, ""

    def _validate_water(self, a: dict, sim: dict) -> tuple[bool, str]:
        target = tuple(a.get("target", []))
        farm = sim["farms"].get(target)
        if farm is None:
            return False, f"No tile at {target}."
        if farm.get("status") not in ("GROWING", "SEEDED", "PLANTED"):
            return False, f"Tile {target} has no crop to water."
        return True, ""

    def _validate_harvest(self, a: dict, sim: dict) -> tuple[bool, str]:
        target = tuple(a.get("target", []))
        farm = sim["farms"].get(target)
        if farm is None:
            return False, f"No tile at {target}."
        if farm.get("status") != "MATURE":
            return False, f"Crop at {target} is not mature."
        return True, ""

    def _validate_plant(self, a: dict, sim: dict) -> tuple[bool, str]:
        target = tuple(a.get("target", []))
        farm = sim["farms"].get(target)
        if farm is None:
            return False, f"No tile at {target}."
        if farm.get("locked", False):
            return False, f"Tile {target} is LOCKED."
        if farm.get("status") not in ("EMPTY",):
            return False, f"Tile {target} is not empty (status={farm.get('status')})."
        crop = a.get("crop", "")
        seed_key = f"{crop}_SEED"
        if sim["seeds"].get(seed_key, 0) < 1 and sim["shed"].get(seed_key, 0) < 1:
            return False, f"No {seed_key} available."
        return True, ""

    def _validate_fertilize(self, a: dict, sim: dict) -> tuple[bool, str]:
        if sim["fertilizer"] < 1:
            return False, "No FERTILIZER available."
        target = tuple(a.get("target", []))
        farm = sim["farms"].get(target)
        if farm is None:
            return False, f"No tile at {target}."
        if farm.get("status") not in ("GROWING", "SEEDED", "PLANTED"):
            return False, f"No growing crop at {target}."
        return True, ""

    def _validate_feed(self, a: dict, sim: dict) -> tuple[bool, str]:
        if sim["feed"] < 1:
            return False, "No FEED available."
        return True, ""

    def _validate_buy_animal(self, a: dict, sim: dict) -> tuple[bool, str]:
        kind = a.get("kind_animal", "")
        rules = cfg.ANIMAL_RULES.get(kind)
        if rules is None:
            return False, f"Unknown animal: {kind}."
        if rules["structure"] not in sim["structures"]:
            return False, f"Missing structure {rules['structure']}."
        if sim["cash"] < rules["cost"]:
            return False, f"Insufficient cash ({sim['cash']} < {rules['cost']})."
        return True, ""

    def _validate_collect(self, a: dict, sim: dict) -> tuple[bool, str]:
        # Basic check; full animal state lives in AnimalManager
        return True, ""

    def _validate_buy_land(self, a: dict, sim: dict) -> tuple[bool, str]:
        if sim["cash"] < cfg.LAND_COST:
            return False, f"Insufficient cash for land ({sim['cash']} < {cfg.LAND_COST})."
        return True, ""

    def _validate_hire(self, a: dict, sim: dict) -> tuple[bool, str]:
        hire_index = int(a.get("hire_index", 0))
        cost = cfg.HIRE_COSTS[min(hire_index, len(cfg.HIRE_COSTS) - 1)]
        if sim["cash"] < cost:
            return False, f"Insufficient cash to hire (need ${cost}, have ${sim['cash']})."
        return True, ""

    def _validate_build_structure(self, a: dict, sim: dict) -> tuple[bool, str]:
        structure_type = a.get("structure_type", "")
        if not structure_type:
            return False, "BUILD_STRUCTURE missing structure_type."
        # Find cost from config
        cost = 0.0
        for rules in cfg.ANIMAL_RULES.values():
            if rules.get("structure") == structure_type:
                cost = rules.get("structure_cost", 0.0)
                break
        if sim["cash"] < cost:
            return False, f"Insufficient cash to build {structure_type} (need ${cost}, have ${sim['cash']:.2f})."
        if structure_type in sim["structures"]:
            return False, f"{structure_type} already built."
        return True, ""

    def _validate_place_animal(self, a: dict, sim: dict) -> tuple[bool, str]:
        # Basic check — full animal carry state lives in AnimalManager
        if not a.get("animal_id"):
            return False, "PLACE_ANIMAL missing animal_id."
        target = a.get("target")
        if not target or len(target) < 2:
            return False, "PLACE_ANIMAL missing target coordinates."
        return True, ""

    # ── state mutation after acceptance ──────────────────────────────────────

    def _apply(self, action: dict, sim: dict) -> None:
        """Update simulated state after an accepted action (BR-012)."""
        kind = action.get("kind", "")

        if kind == "SELL":
            product = action.get("product", "")
            units = int(action.get("units", 0))
            sim["shed"][product] = sim["shed"].get(product, 0) - units
            sim["market_orders_used"] += 1

        elif kind == "PLANT":
            crop = action.get("crop", "")
            seed_key = f"{crop}_SEED"
            if sim["seeds"].get(seed_key, 0) > 0:
                sim["seeds"][seed_key] -= 1
            target = tuple(action.get("target", []))
            if target in sim["farms"]:
                sim["farms"][target]["status"] = "SEEDED"

        elif kind == "FERTILIZE":
            sim["fertilizer"] = max(0, sim["fertilizer"] - 1)

        elif kind == "FEED":
            sim["feed"] = max(0, sim["feed"] - 1)

        elif kind == "BUY_ANIMAL":
            kind_animal = action.get("kind_animal", "")
            rules = cfg.ANIMAL_RULES.get(kind_animal, {})
            sim["cash"] -= rules.get("cost", 0)

        elif kind == "BUY_LAND":
            sim["cash"] -= cfg.LAND_COST

        elif kind == "HIRE":
            hire_index = int(action.get("hire_index", 0))
            cost = cfg.HIRE_COSTS[min(hire_index, len(cfg.HIRE_COSTS) - 1)]
            sim["cash"] -= cost

        elif kind == "BUILD_STRUCTURE":
            structure_type = action.get("structure_type", "")
            for rules in cfg.ANIMAL_RULES.values():
                if rules.get("structure") == structure_type:
                    sim["cash"] -= rules.get("structure_cost", 0.0)
                    break
            if structure_type and structure_type not in sim["structures"]:
                sim["structures"].append(structure_type)
