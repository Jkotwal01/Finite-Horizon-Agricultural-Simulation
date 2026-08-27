"""
api/routes.py — FastAPI route definitions.

REST API surface for the simulation dashboard.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import APIRouter, HTTPException
from api.schemas import (
    StartRequest, RunRequest, SimulationResponse,
    StepResponse, RunNResponse, ReportResponse,
    TerminalResponse, ConfigResponse,
)
from engine.simulator import Simulator
import config as cfg

router = APIRouter()

# Single shared simulator instance (in-memory session per server process)
_sim: Simulator = Simulator()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "Agricultural Simulation API"}


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/api/config", response_model=ConfigResponse)
def get_config():
    """Return game constants and rule tables."""
    return ConfigResponse(
        total_turns=cfg.TOTAL_TURNS,
        turns_per_day=cfg.TURNS_PER_DAY,
        shed_capacity=cfg.SHED_CAPACITY,
        worker_capacity=cfg.WORKER_CAPACITY,
        max_orders=cfg.MAX_ORDERS,
        price_floor=cfg.PRICE_FLOOR,
        endgame_threshold=cfg.ENDGAME_THRESHOLD,
        crop_rules=cfg.CROP_RULES,
        animal_rules=cfg.ANIMAL_RULES,
        hire_costs=cfg.HIRE_COSTS,
    )


# ── Simulation lifecycle ──────────────────────────────────────────────────────

@router.post("/api/simulate/start")
def start_simulation(req: StartRequest = StartRequest()):
    """Start (or restart) a fresh simulation."""
    global _sim
    _sim = Simulator()
    result = _sim.start(initial_cash=req.initial_cash)
    return result


@router.get("/api/simulate/state")
def get_state():
    """Get current simulation state snapshot."""
    if not _sim.is_running and _sim.current_turn == 0:
        raise HTTPException(status_code=400, detail="Simulation not started.")
    return _sim.get_state_dict()


@router.post("/api/simulate/step")
def step_simulation():
    """Advance the simulation by exactly one turn."""
    if not _sim.is_running and _sim.current_turn >= cfg.TOTAL_TURNS:
        raise HTTPException(status_code=400, detail="Simulation already finished.")
    if not _sim.is_running and _sim.current_turn == 0:
        raise HTTPException(status_code=400, detail="Simulation not started.")
    return _sim.step()


@router.post("/api/simulate/run")
def run_simulation(req: RunRequest = RunRequest(turns=24)):
    """Run N turns at once (default: 24 = one full day)."""
    if not _sim.is_running and _sim.current_turn == 0:
        raise HTTPException(status_code=400, detail="Simulation not started.")
    return _sim.run_n_turns(req.turns)


@router.post("/api/simulate/run-full")
def run_full_simulation():
    """Run all 720 turns in one call and return the terminal result."""
    global _sim
    if not _sim.is_running and _sim.current_turn == 0:
        # Auto-start if not started
        _sim.start()
    result = _sim.run_n_turns(cfg.TOTAL_TURNS)
    return result


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/api/simulate/report")
def get_report():
    """Return the EvaluationReport collected so far."""
    report = _sim.telemetry.report.to_dict()
    report["release_gate"] = _sim.telemetry.release_gate()
    return report


@router.get("/api/simulate/terminal")
def get_terminal():
    """Return TerminalResult (only meaningful at or after Turn 720)."""
    if _sim.current_turn < cfg.TOTAL_TURNS and _sim.is_running:
        # Compute a preliminary estimate
        pass
    terminal = _sim._compute_terminal()
    return terminal.to_dict()
