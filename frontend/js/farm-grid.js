/**
 * farm-grid.js — 5×5 farm board renderer
 */
"use strict";

const TILE_ICONS = {
  EMPTY:   "⬜",
  PLANTED: "🌱",
  GROWING: "🌿",
  MATURE:  "🌾",
  DEAD:    "💀",
  LOCKED:  "🔒",
};

const CROP_ICONS = {
  WHEAT:      "🌾",
  TOMATO:     "🍅",
  STRAWBERRY: "🍓",
};

const ANIMAL_ICONS = {
  COW: "🐄",
  CHICKEN: "🐔"
};

/**
 * Render the dynamic farm grid.
 * @param {Array} farms   - array of tile objects from API
 * @param {Array} crops   - array of crop objects from API
 * @param {Array} animals - array of animal objects from API
 */
function renderFarmGrid(farms, crops, animals) {
  const grid = document.getElementById("farm-grid");
  if (!grid) return;

  // Build crop lookup by tile position
  const cropMap = {};
  if (crops) {
    crops.forEach(c => {
      cropMap[`${c.tile_row},${c.tile_col}`] = c;
    });
  }

  // Build animal lookup by tile position (for PLACED animals)
  const animalMap = {};
  if (animals) {
    animals.forEach(a => {
      if (a.location === 'PLACED') {
        animalMap[`${a.tile_row},${a.tile_col}`] = a;
      }
    });
  }

  // Calculate dynamic grid size (FR-010 board expansion)
  let maxCol = 4; // minimum 5 columns (0 to 4)
  if (farms && farms.length > 0) {
    maxCol = Math.max(...farms.map(f => f.col));
  }
  grid.style.setProperty("--board-cols", maxCol + 1);

  grid.innerHTML = "";

  // Sort farms by row then col for consistent rendering
  const sorted = [...farms].sort((a, b) => a.row - b.row || a.col - b.col);

  sorted.forEach(tile => {
    const key = `${tile.row},${tile.col}`;
    const crop = cropMap[key];
    const animal = animalMap[key];

    const div = document.createElement("div");
    div.className = `farm-tile status-${tile.status || "EMPTY"}`;
    div.setAttribute("role", "gridcell");
    div.setAttribute("aria-label", `Tile ${tile.row},${tile.col}: ${tile.status}`);
    div.title = buildTileTooltip(tile, crop, animal);

    // Icon
    let icon = TILE_ICONS[tile.status] || "⬜";
    if (crop && !crop.is_dead) {
      icon = CROP_ICONS[crop.crop] || icon;
    } else if (animal && tile.status === 'ANIMAL') {
      icon = ANIMAL_ICONS[animal.kind] || "🐄";
    }

    // Label (crop name, animal name, or tile coords)
    let label = `${tile.row},${tile.col}`;
    if (crop) label = `${crop.crop} A${crop.age}`;
    if (animal) label = `${animal.kind}`;
    if (tile.locked) { icon = "🔒"; label = "LOCKED"; }

    div.innerHTML = `
      <span class="tile-emoji">${icon}</span>
      <span class="tile-label">${label}</span>
    `;

    grid.appendChild(div);
  });
}

function buildTileTooltip(tile, crop, animal) {
  let tooltip = `(${tile.row},${tile.col}) ${tile.status}`;
  
  if (crop) {
    tooltip = `(${tile.row},${tile.col}) ${crop.crop}\n` +
    `Age: ${crop.age} turns\n` +
    `Water: ${crop.water_status}\n` +
    `Fertilized: ${crop.fertilized}\n` +
    `Yield: ${crop.yield_units} units\n` +
    (crop.is_mature ? "✅ MATURE" : `Matures in ~${Math.max(0,48-crop.age)} turns`);
  } else if (animal) {
    tooltip = `(${tile.row},${tile.col}) ${animal.kind}\n` +
    `ID: ${animal.animal_id}\n` +
    `Alive: ${animal.is_alive ? 'Yes' : 'No'}\n` +
    `Fed: ${animal.fed ? 'Yes ✅' : 'No ❌'}\n` +
    `Missed Feeds: ${animal.consecutive_missed_feed}\n` +
    `Product Ready: ${animal.product_ready}`;
  }
  return tooltip;
}
