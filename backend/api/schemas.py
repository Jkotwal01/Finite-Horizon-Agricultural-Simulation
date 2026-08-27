"""
api/schemas.py — Pydantic request/response schemas for FastAPI.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional


class StartRequest(BaseModel):
    initial_cash: float = Field(default=500.0, ge=0, description="Starting cash")


class RunRequest(BaseModel):
    turns: int = Field(default=1, ge=1, le=720, description="Number of turns to run")


class SimulationResponse(BaseModel):
    status: str
    turn: int
    state: dict[str, Any] = {}
    message: str = ""


class StepResponse(BaseModel):
    status: str
    turn: int
    elapsed_ms: float = 0.0
    is_endgame: bool = False
    remaining_turns: int = 0
    tasks_assigned: int = 0
    actions_accepted: int = 0
    actions_rejected: int = 0
    crop_events: list[dict] = []
    animal_events: list[dict] = []
    warehouse: dict = {}
    state: dict[str, Any] = {}
    terminal: Optional[dict] = None
    error: Optional[str] = None


class RunNResponse(BaseModel):
    turns_run: int
    current_turn: int
    is_finished: bool
    last_result: dict[str, Any] = {}


class ReportResponse(BaseModel):
    turns: int
    exceptions: int
    invalid_actions: int
    terminal_wealth: float
    crop_deaths: int
    animal_deaths: int
    warehouse_overflows: int
    per_turn_wealth: list[float] = []
    action_log: list[dict] = []
    release_gate: dict = {}


class TerminalResponse(BaseModel):
    turn: int
    terminal_wealth: float
    cash: float
    inventory_value: float
    asset_value: float
    penalties: float
    unrealizable_production: float
    exceptions: int
    invalid_actions: int
    component_ledger: dict = {}


class ConfigResponse(BaseModel):
    total_turns: int
    turns_per_day: int
    shed_capacity: int
    worker_capacity: int
    max_orders: int
    price_floor: float
    endgame_threshold: int
    crop_rules: dict
    animal_rules: dict
    hire_costs: list[float]
