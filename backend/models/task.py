"""
models/task.py — Task and Assignments data classes.

FR-017: Task scheduling schema.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class Task:
    """
    A single unit of work to be assigned to a worker.

    Priority: higher number = more urgent (survival=100 beats economic=10).
    """
    task_id: str
    kind: str                              # "WATER","HARVEST","PLANT","SELL","FEED","FERTILIZE","BUY_ANIMAL","COLLECT"
    priority: int                          # see config.py PRIORITY_* constants
    value: float = 0.0                     # expected monetary value of completing this task
    target: Optional[list[int]] = None     # [row, col]
    worker_id: Optional[int] = None        # assigned after scheduling
    resource_reservation: dict = field(default_factory=dict)
    preconditions: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)  # extra context (crop type, units, etc.)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "priority": self.priority,
            "value": self.value,
            "target": self.target,
            "worker_id": self.worker_id,
            "resource_reservation": self.resource_reservation,
            "metadata": self.metadata,
        }


@dataclass
class Assignments:
    """
    The result of the task scheduling step: ordered task→worker mapping.
    """
    assignments: list[Task] = field(default_factory=list)
    unassigned: list[Task] = field(default_factory=list)
    worker_load: dict[int, list[str]] = field(default_factory=dict)  # worker_id → [task_id]

    def to_dict(self) -> dict:
        return {
            "assignments": [t.to_dict() for t in self.assignments],
            "unassigned": [t.to_dict() for t in self.unassigned],
            "worker_load": {str(k): v for k, v in self.worker_load.items()},
        }
