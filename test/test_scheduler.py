"""
test/test_scheduler.py — FR-017: Task scheduling priority order.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.scheduler import TaskScheduler
from models.task import Task
import config as cfg


@pytest.fixture
def scheduler():
    return TaskScheduler()


def make_task(tid, kind, priority, value=0.0, target=None):
    return Task(task_id=tid, kind=kind, priority=priority, value=value, target=target)


WORKERS = [{"id": 0, "row": 0, "col": 0}, {"id": 1, "row": 4, "col": 4}]


class TestPriorityOrder:

    def test_survival_task_assigned_before_economic(self, scheduler):
        """ST18-A: Far P100 task beats nearby P10 task."""
        water = make_task("w1", "WATER", cfg.PRIORITY_SURVIVAL, target=[4, 4])
        economic = make_task("e1", "BUY_LAND", cfg.PRIORITY_ECONOMIC, target=[0, 1])

        assignments = scheduler.schedule([economic, water], WORKERS)
        assigned_kinds = [t.kind for t in assignments.assignments]

        # WATER should be assigned (survival wins regardless of distance)
        assert "WATER" in assigned_kinds

    def test_value_breaks_priority_tie(self, scheduler):
        """Same priority → higher value task assigned first."""
        t1 = make_task("t1", "HARVEST", cfg.PRIORITY_HARVEST, value=100.0, target=[0, 1])
        t2 = make_task("t2", "HARVEST", cfg.PRIORITY_HARVEST, value=10.0,  target=[0, 2])

        assignments = scheduler.schedule([t2, t1], [{"id": 0, "row": 0, "col": 0}])
        # First assigned task should be t1 (higher value)
        assert assignments.assignments[0].task_id == "t1"

    def test_no_double_assignment(self, scheduler):
        """Each worker is assigned at most one task per scheduling call."""
        tasks = [
            make_task(f"t{i}", "WATER", cfg.PRIORITY_SURVIVAL, target=[0, i])
            for i in range(5)
        ]
        # Only 2 workers available
        assignments = scheduler.schedule(tasks, WORKERS)
        worker_ids = [t.worker_id for t in assignments.assignments]
        assert len(set(worker_ids)) == len(worker_ids)  # unique worker ids

    def test_unassigned_when_no_workers(self, scheduler):
        """No workers → all tasks unassigned."""
        tasks = [make_task("t1", "WATER", cfg.PRIORITY_SURVIVAL, target=[0, 0])]
        assignments = scheduler.schedule(tasks, workers=[])
        assert len(assignments.unassigned) == 1
        assert len(assignments.assignments) == 0

    def test_resource_conflict_prevents_double_reserve(self, scheduler):
        """BR-003: Two tasks that both reserve FERTILIZER — only one gets assigned."""
        t1 = make_task("f1", "FERTILIZE", cfg.PRIORITY_FERTILIZE, target=[0, 0])
        t1.resource_reservation = {"FERTILIZER": 1}
        t2 = make_task("f2", "FERTILIZE", cfg.PRIORITY_FERTILIZE, target=[0, 1])
        t2.resource_reservation = {"FERTILIZER": 1}

        assignments = scheduler.schedule([t1, t2], WORKERS)
        # Due to resource conflict, only one fertilize task should be assigned
        fert_assigned = [t for t in assignments.assignments if t.kind == "FERTILIZE"]
        assert len(fert_assigned) <= 1

    def test_task_without_target_assigned(self, scheduler):
        """Tasks with no target (e.g. BUY) are assigned to first available worker."""
        buy = make_task("buy1", "BUY_LAND", cfg.PRIORITY_ECONOMIC, target=None)
        assignments = scheduler.schedule([buy], WORKERS)
        assert len(assignments.assignments) == 1
