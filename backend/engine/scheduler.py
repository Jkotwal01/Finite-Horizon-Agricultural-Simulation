"""
engine/scheduler.py — TaskScheduler (FR-017).

Assigns tasks to workers using:
  Priority (highest first) → Value (highest first) → Distance (lowest first).

Rules:
- BR-001 Survival first (PRIORITY_SURVIVAL tasks never displaced).
- BR-002 Priority before distance (distance cannot override urgency).
- BR-003 Resource reservation (no double-assignment of same resource).
- One worker can only be assigned one task per scheduling call unless tasks
  are non-conflicting (we keep it simple: one task per worker per pass).
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.task import Task, Assignments
from engine.movement import MovementEngine
import config as cfg


class TaskScheduler:
    """
    Collects mandatory + optional tasks and assigns them to available workers.
    """

    def __init__(self) -> None:
        self._movement = MovementEngine()

    def schedule(
        self,
        tasks: list[Task],
        workers: list[dict],
        rows: int = cfg.BOARD_ROWS,
        cols: int = cfg.BOARD_COLS,
        locked_tiles: set | None = None,
    ) -> Assignments:
        """
        Assign tasks to workers.

        workers: list of dicts with keys 'id', 'row', 'col'.
        Returns Assignments with assignments, unassigned, worker_load.
        """
        if locked_tiles is None:
            locked_tiles = set()

        # Sort tasks: priority DESC, value DESC (distance is tie-breaker below)
        sorted_tasks = sorted(tasks, key=lambda t: (-t.priority, -t.value))

        assigned_tasks: list[Task] = []
        unassigned_tasks: list[Task] = []
        worker_busy: set[int] = set()
        reserved_resources: dict[str, int] = {}
        worker_load: dict[int, list[str]] = {w["id"]: [] for w in workers}

        for task in sorted_tasks:
            # Check resource conflicts (BR-003)
            if self._resource_conflict(task, reserved_resources):
                unassigned_tasks.append(task)
                continue

            # Find the best available worker (distance as tie-breaker)
            best_worker = self._find_best_worker(
                task, workers, worker_busy, rows, cols, locked_tiles
            )

            if best_worker is None:
                unassigned_tasks.append(task)
                continue

            # Assign
            task.worker_id = best_worker["id"]
            worker_busy.add(best_worker["id"])
            assigned_tasks.append(task)
            worker_load[best_worker["id"]].append(task.task_id)

            # Reserve resources
            for resource, units in task.resource_reservation.items():
                reserved_resources[resource] = (
                    reserved_resources.get(resource, 0) + units
                )

        return Assignments(
            assignments=assigned_tasks,
            unassigned=unassigned_tasks,
            worker_load=worker_load,
        )

    # ── private helpers ───────────────────────────────────────────────────────

    def _resource_conflict(
        self, task: Task, reserved: dict[str, int]
    ) -> bool:
        """Returns True if any resource needed by this task is already reserved."""
        for resource, units in task.resource_reservation.items():
            if reserved.get(resource, 0) + units > reserved.get(resource + "_total", units + 1):
                # Simplified check: if resource already reserved by anyone, skip
                if resource in reserved:
                    return True
        return False

    def _find_best_worker(
        self,
        task: Task,
        workers: list[dict],
        busy: set[int],
        rows: int,
        cols: int,
        locked: set,
    ) -> dict | None:
        """Find closest available worker to the task target."""
        available = [w for w in workers if w["id"] not in busy]
        if not available:
            return None
        if task.target is None:
            # No target (e.g. BUY action) — assign first available worker
            return available[0]

        target = (task.target[0], task.target[1])
        best = None
        best_dist = float("inf")
        for worker in available:
            result = self._movement.find_path(
                start=(worker["row"], worker["col"]),
                target=target,
                rows=rows,
                cols=cols,
                locked_tiles=locked,
            )
            if result.reachable and result.distance < best_dist:
                best_dist = result.distance
                best = worker
        return best
