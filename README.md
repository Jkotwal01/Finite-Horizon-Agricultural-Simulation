# 🌾 AgriSim — Finite-Horizon Agricultural Simulation

An AI-driven farm management simulation built as an internship project.
The AI "brain" autonomously manages crops, animals, warehouse, and market to
**maximize Terminal Wealth** at the end of **720 turns** (30 days × 24 turns/day).

---

## 🏗️ Architecture

```
project/
├── backend/
│   ├── main.py          # FastAPI entrypoint (serves API + frontend)
│   ├── config.py        # ALL game constants (single source of truth)
│   ├── models/          # Pure data classes (state, crop, animal, task, report)
│   └── engine/          # Business logic classes (one per functional unit)
│       ├── observation.py   # FR-001: Raw → CanonicalState
│       ├── state_manager.py # FR-003: Persistent state + deltas
│       ├── crop_manager.py  # FR-005/006/007: Plant, water, fertilize, harvest
│       ├── animal_manager.py# FR-008/009: Buy, carry, place, feed, collect
│       ├── movement.py      # FR-004: BFS pathfinding
│       ├── warehouse.py     # FR-012: 100-unit capacity, overflow detection
│       ├── market.py        # FR-013/014: Marginal pricing, demand events
│       ├── forecast.py      # FR-015: Production forecasting
│       ├── scheduler.py     # FR-017: Priority→Value→Distance task assignment
│       ├── validator.py     # FR-018: Sequential action validation
│       ├── strategy.py      # FR-010/011/019: Land/labor economics, replanning
│       ├── endgame.py       # FR-020: Liquidation mode at Turn 670+
│       ├── telemetry.py     # FR-021: Timing, errors, release gate
│       └── simulator.py     # Main turn-loop orchestrator (WF-01 to WF-06)
├── frontend/
│   ├── index.html       # Dashboard (3-column layout)
│   ├── css/style.css    # Dark glassmorphism theme
│   └── js/
│       ├── app.js       # REST API calls + UI updates
│       ├── farm-grid.js # 5×5 board renderer
│       └── charts.js    # Wealth chart (Chart.js)
├── test/                # pytest test suite (13 test files)
├── requirements.txt
└── render.yaml          # Free deployment on Render.com
```

---

## 🚀 Quick Start (Local)

### 1. Install dependencies

```bash
cd project
pip install -r requirements.txt
```

### 2. Run the server

```bash
cd project
uvicorn backend.main:app --reload
```

### 3. Open the dashboard

```
http://localhost:8000
```

### 4. Use the API directly

```
http://localhost:8000/docs   ← Interactive Swagger UI
```

---

## 🌐 REST API

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/simulate/start` | Start a fresh simulation |
| `GET`  | `/api/simulate/state` | Current game state |
| `POST` | `/api/simulate/step`  | Advance 1 turn |
| `POST` | `/api/simulate/run`   | Run N turns (`{"turns": 24}`) |
| `POST` | `/api/simulate/run-full` | Run all 720 turns |
| `GET`  | `/api/simulate/report` | EvaluationReport + release gate |
| `GET`  | `/api/simulate/terminal` | TerminalResult (final score) |
| `GET`  | `/api/config` | Game constants |
| `GET`  | `/health` | Health check |

---

## 🧪 Running Tests

```bash
cd project
pytest test/ -v --tb=short
```

Expected output: **~60+ tests across 13 files** covering all major FR requirements.

---

## 🎮 Core Game Rules

| Mechanic | Rule |
|----------|------|
| Turn limit | 720 turns (30 days × 24 turns/day) |
| Warehouse | Max 100 units (seeds excluded) |
| Market orders | Max 10 per turn |
| Worker inventory | Max 10 units each |
| Watering | Must water every turn — miss 2 → crop dies |
| Feeding | Must feed daily — miss 2 → animal dies |
| Endgame | Turn 670+ → stop investing, liquidate everything |
| Scoring | `Terminal Wealth = Cash + Inventory Value − Penalties` |

---

## 📊 Features Implemented (~58%)

### Core (FR-001 to FR-009)
- ✅ Observation normalization → CanonicalState
- ✅ Time/horizon tracking (never negative remaining turns)
- ✅ Persistent state with deltas
- ✅ BFS movement engine (non-square boards, LOCKED tiles)
- ✅ Full crop lifecycle (plant, water, fertilize, harvest)
- ✅ Ongoing crops with unlimited production (no cap)
- ✅ Fertilizer window enforcement + resource reservation
- ✅ Animal lifecycle (buy, carry, place, feed, collect)
- ✅ Mandatory survival task priority

### Economics & Strategy (FR-010 to FR-019)
- ✅ Land ROI evaluation (BUY vs WAIT)
- ✅ Labor ROI evaluation (HIRE vs WAIT)
- ✅ 100-unit warehouse with 85/90/100% overflow thresholds
- ✅ Marginal unit pricing with price floor
- ✅ Dated demand events forecast
- ✅ Full production forecast (crops + animals)
- ✅ Task scheduling (Priority → Value → Distance)
- ✅ Sequential action validation (BR-012)
- ✅ Bounded counterfactual replanning (stub)

### Endgame & Telemetry (FR-020 to FR-022)
- ✅ Endgame mode at Turn 670+
- ✅ Viability check — no non-viable planting (BR-011)
- ✅ Full inventory liquidation
- ✅ Per-turn telemetry (timing, exceptions, deaths, overflows)
- ✅ Release gate (FR-021)
- ✅ Terminal result with component ledger (FR-022)

---

## 🌍 Free Deployment (Render.com)

1. Push the `project/` directory to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set root directory to `project`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

The `render.yaml` file automates all of this.

---

## 📝 Design Principles

- **OOP throughout** — every functional unit is its own class
- **Single config source** — `config.py` is the only place with game constants
- **No over-engineering** — no database, no Redis, no message queues
- **Sequential validation** — actions are validated in order against the evolving simulated state
- **Beginner-friendly** — clear docstrings, explicit error messages, simple imports
