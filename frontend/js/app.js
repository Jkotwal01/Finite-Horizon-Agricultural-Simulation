/**
 * app.js — Main dashboard JS
 * Connects frontend to FastAPI backend via REST.
 */
"use strict";

const API = "";  // same-origin; prefix empty (served by FastAPI)

// ── State ──────────────────────────────────────────────────────
let currentTurn = 0;
let totalTasaksAssigned = 0;
let isRunning = false;

// ── Init ───────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  initWealthChart();
  renderFarmGrid(buildEmptyFarms(), []);
  log("Ready. Click Start to begin.", "info", "—");
});

// ── Button actions ─────────────────────────────────────────────
async function simStart() {
  try {
    const res = await api("POST", "/api/simulate/start", { initial_cash: 500 });
    isRunning = true;
    enableButtons(true);
    log("Simulation started. Turn 0 initialized.", "ok", 0);
    updateAll(res.state, null, 0);
  } catch (e) {
    log(`Start failed: ${e.message}`, "error", "—");
  }
}

async function simStep() {
  try {
    setStatus("Running 1 turn…");
    const res = await api("POST", "/api/simulate/step");
    handleStepResult(res);
  } catch (e) {
    log(`Step error: ${e.message}`, "error", currentTurn);
  }
}

async function simDay() {
  try {
    setStatus("Running 1 day (24 turns)…");
    const res = await api("POST", "/api/simulate/run", { turns: 24 });
    handleRunResult(res);
  } catch (e) {
    log(`Day run error: ${e.message}`, "error", currentTurn);
  }
}

async function simFull() {
  try {
    setStatus("Running full 720 turns… please wait.");
    const res = await api("POST", "/api/simulate/run-full");
    handleRunResult(res);
  } catch (e) {
    log(`Full run error: ${e.message}`, "error", currentTurn);
  }
}

// ── Result handlers ────────────────────────────────────────────
function handleStepResult(res) {
  if (res.error) { log(`Error: ${res.error}`, "error", res.turn); return; }
  currentTurn = res.turn || 0;
  totalTasaksAssigned += res.tasks_assigned || 0;

  updateAll(res.state, res, currentTurn);

  const msg = [
    `T${currentTurn}`,
    `✔ ${res.actions_accepted} actions`,
    res.actions_rejected > 0 ? `✘ ${res.actions_rejected} rejected` : "",
    res.elapsed_ms ? `${res.elapsed_ms.toFixed(1)}ms` : "",
  ].filter(Boolean).join(" | ");
  log(msg, res.actions_rejected > 0 ? "warn" : "ok", currentTurn);

  // Crop events
  (res.crop_events || []).forEach(e => {
    const emoji = e.type === "DEAD" ? "💀" : e.type === "MATURED" ? "🌾" : "🔄";
    log(`${emoji} Crop ${e.type}: ${e.crop?.crop} @(${e.crop?.tile_row},${e.crop?.tile_col})`,
        e.type === "DEAD" ? "error" : "info", currentTurn);
  });

  if (res.terminal) showTerminal(res.terminal);
  setStatus(res.is_endgame ? "🔴 ENDGAME MODE — Liquidating…" : `Turn ${currentTurn} / 720`);
}

function handleRunResult(res) {
  const last = res.last_result || {};
  currentTurn = res.current_turn || 0;
  if (last.state) updateAll(last.state, last, currentTurn);

  log(`Ran ${res.turns_run} turns → Turn ${res.current_turn}`, "ok", currentTurn);

  if (res.is_finished || last.terminal) {
    const t = last.terminal;
    if (t) showTerminal(t);
    enableButtons(false);
    setStatus(`✅ Simulation complete! Terminal Wealth: $${t?.terminal_wealth?.toFixed(2) || "?"}`);
    // Fetch full report
    fetchReport();
  } else {
    setStatus(`Running… Turn ${currentTurn} / 720`);
  }
}

// ── UI update helpers ──────────────────────────────────────────
function updateAll(state, result, turn) {
  if (!state) return;

  // Header stats
  setText("stat-turn", turn);
  setText("stat-day", state.day ?? "—");
  setText("stat-cash", `$${(state.cash ?? 0).toFixed(2)}`);

  // Progress bar
  const pct = Math.min(100, (turn / 720) * 100);
  document.getElementById("progress-bar").style.width = `${pct}%`;
  document.getElementById("progress-label").textContent = `${turn} / 720 turns`;

  // Endgame badge
  const badge = document.getElementById("endgame-badge");
  if (state.is_endgame) badge.style.display = "flex";
  else badge.style.display = "none";

  // Estimated wealth
  const invVal = calcInventoryValue(state.shed_inventory || {});
  const wealth = (state.cash || 0) + invVal;
  setText("stat-wealth", `$${wealth.toFixed(2)}`);

  // Chart
  updateWealthChart(turn, state.cash || 0, wealth);

  // Farm grid
  renderFarmGrid(state.farms || [], state.crops || []);

  // Warehouse
  updateWarehouse(state.warehouse_total || 0, state.warehouse_capacity || 100, state.shed_inventory || {}, state.seeds || {});

  // Crops list
  renderCrops(state.crops || []);

  // Animals list
  renderAnimals(state.animals || []);

  // Telemetry
  if (result) {
    addMetric("m-tasks", result.tasks_assigned || 0);
  }

  // Fetch report for telemetry periodically
  if (turn % 24 === 0 && turn > 0) fetchReport();
}

// ── Warehouse ──────────────────────────────────────────────────
function updateWarehouse(total, capacity, shed, seeds) {
  const pct = Math.min(100, (total / capacity) * 100);
  const bar = document.getElementById("warehouse-bar");
  bar.style.width = `${pct}%`;
  bar.className = `warehouse-bar${pct >= 85 ? " danger" : ""}`;
  document.getElementById("warehouse-label").textContent =
    `${total} / ${capacity} units (${pct.toFixed(0)}%)`;

  // Inventory chips
  const list = document.getElementById("inventory-list");
  const allInv = { ...shed };
  // Add seeds
  Object.entries(seeds || {}).forEach(([k, v]) => { if (v > 0) allInv[k] = v; });

  if (Object.keys(allInv).length === 0) {
    list.innerHTML = `<span style="color:var(--text-muted);font-size:0.75rem">Warehouse empty</span>`;
    return;
  }
  list.innerHTML = Object.entries(allInv)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `<div class="inv-chip"><span class="inv-name">${k}</span><span class="inv-qty">${v}</span></div>`)
    .join("");
}

// ── Crops ──────────────────────────────────────────────────────
const CROP_EMOJI = { WHEAT: "🌾", TOMATO: "🍅", STRAWBERRY: "🍓" };

function renderCrops(crops) {
  const list = document.getElementById("crops-list");
  const alive = crops.filter(c => !c.is_dead);
  if (alive.length === 0) {
    list.innerHTML = `<span style="color:var(--text-muted);font-size:0.75rem">No active crops</span>`;
    return;
  }
  list.innerHTML = alive.map(c => {
    const status = c.is_mature ? "MATURE" : c.water_status === "DEAD" ? "DEAD" : "GROWING";
    const badgeClass = { MATURE: "badge-mature", DEAD: "badge-dead", GROWING: "badge-ok" }[status] || "badge-ok";
    return `
      <div class="entity-row">
        <span class="entity-icon">${CROP_EMOJI[c.crop] || "🌱"}</span>
        <div class="entity-info">
          <div class="entity-name">${c.crop}</div>
          <div class="entity-detail">Age ${c.age}t | Yield ${c.yield_units}u | (${c.tile_row},${c.tile_col})${c.fertilized ? " 🧪" : ""}</div>
        </div>
        <span class="entity-badge ${badgeClass}">${status}</span>
      </div>
    `;
  }).join("");
}

// ── Animals ────────────────────────────────────────────────────
const ANIMAL_EMOJI = { COW: "🐄", CHICKEN: "🐔" };

function renderAnimals(animals) {
  const list = document.getElementById("animals-list");
  if (!animals || animals.length === 0) {
    list.innerHTML = `<span style="color:var(--text-muted);font-size:0.75rem">No animals</span>`;
    return;
  }
  list.innerHTML = animals.map(a => {
    const status = !a.is_alive ? "DEAD" : a.fed ? "FED" : "HUNGRY";
    const badgeClass = { DEAD: "badge-dead", FED: "badge-ok", HUNGRY: "badge-warn" }[status];
    return `
      <div class="entity-row">
        <span class="entity-icon">${ANIMAL_EMOJI[a.kind] || "🐾"}</span>
        <div class="entity-info">
          <div class="entity-name">${a.kind} (${a.animal_id})</div>
          <div class="entity-detail">${a.location} | Product: ${a.product_ready}u</div>
        </div>
        <span class="entity-badge ${badgeClass}">${status}</span>
      </div>
    `;
  }).join("");
}

// ── Terminal result ────────────────────────────────────────────
function showTerminal(t) {
  const card = document.getElementById("terminal-card");
  const content = document.getElementById("terminal-content");
  card.style.display = "block";
  content.innerHTML = `
    <div class="terminal-row"><span class="terminal-label">💵 Cash</span><span class="terminal-value" style="color:var(--accent-green)">$${(t.cash||0).toFixed(2)}</span></div>
    <div class="terminal-row"><span class="terminal-label">📦 Inventory Value</span><span class="terminal-value">$${(t.inventory_value||0).toFixed(2)}</span></div>
    <div class="terminal-row"><span class="terminal-label">🏚 Asset Value</span><span class="terminal-value">$${(t.asset_value||0).toFixed(2)}</span></div>
    <div class="terminal-row"><span class="terminal-label">⚠️ Penalties</span><span class="terminal-value" style="color:var(--accent-red)">-$${(t.penalties||0).toFixed(2)}</span></div>
    <div class="terminal-row"><span class="terminal-label">🚫 Unrealizable</span><span class="terminal-value" style="color:var(--text-muted)">$${(t.unrealizable_production||0).toFixed(2)}</span></div>
    <div class="terminal-row terminal-total"><span class="terminal-label">🏆 Terminal Wealth</span><span class="terminal-value">$${(t.terminal_wealth||0).toFixed(2)}</span></div>
  `;
}

// ── Report / Telemetry ─────────────────────────────────────────
async function fetchReport() {
  try {
    const r = await api("GET", "/api/simulate/report");
    setText("m-exceptions", r.exceptions || 0);
    setText("m-invalid", r.invalid_actions || 0);
    setText("m-crop-deaths", r.crop_deaths || 0);
    setText("m-animal-deaths", r.animal_deaths || 0);
    setText("m-overflows", r.warehouse_overflows || 0);

    // Log last few actions
    const logEl = document.getElementById("action-log");
    const newEntries = (r.action_log || []).slice(-5);
    // We don't clear the log; just show recent entries via step result
  } catch (_) {}
}

// ── Utilities ──────────────────────────────────────────────────
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function addMetric(id, val) {
  const el = document.getElementById(id);
  if (el) {
    const prev = parseInt(el.textContent) || 0;
    el.textContent = prev + val;
  }
}

function setStatus(msg) {
  const el = document.getElementById("status-msg");
  if (el) el.innerHTML = msg;
}

function log(msg, type = "ok", turn = "—") {
  const container = document.getElementById("action-log");
  if (!container) return;
  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  entry.innerHTML = `<span class="log-turn">T${turn}</span><span class="log-text">${msg}</span>`;
  container.appendChild(entry);
  // Keep last 100 entries
  while (container.children.length > 100) container.removeChild(container.firstChild);
  container.scrollTop = container.scrollHeight;
}

function enableButtons(started) {
  document.getElementById("btn-step").disabled = !started;
  document.getElementById("btn-day").disabled = !started;
  document.getElementById("btn-full").disabled = !started;
}

function buildEmptyFarms() {
  const farms = [];
  for (let r = 0; r < 5; r++)
    for (let c = 0; c < 5; c++)
      farms.push({ row: r, col: c, status: "EMPTY", locked: false });
  return farms;
}

function calcInventoryValue(inv) {
  const prices = { WHEAT: 8, TOMATO: 10, STRAWBERRY: 12, MILK: 15, EGGS: 5 };
  return Object.entries(inv).reduce((sum, [p, u]) => sum + (prices[p] || 0) * u, 0);
}
