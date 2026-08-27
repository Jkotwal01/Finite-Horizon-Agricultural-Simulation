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

/**
 * Render the 5×5 farm grid.
 * @param {Array} farms  - array of tile objects from API
 * @param {Array} crops  - array of crop objects from API
 */
function renderFarmGrid(farms, crops) {
  const grid = document.getElementById("farm-grid");
  if (!grid) return;

  // Build crop lookup by tile position
  const cropMap = {};
  if (crops) {
    crops.forEach(c => {
      cropMap[`${c.tile_row},${c.tile_col}`] = c;
    });
  }

  grid.innerHTML = "";

  // Sort farms by row then col for consistent rendering
  const sorted = [...farms].sort((a, b) => a.row - b.row || a.col - b.col);

  sorted.forEach(tile => {
    const key = `${tile.row},${tile.col}`;
    const crop = cropMap[key];

    const div = document.createElement("div");
    div.className = `farm-tile status-${tile.status || "EMPTY"}`;
    div.setAttribute("role", "gridcell");
    div.setAttribute("aria-label", `Tile ${tile.row},${tile.col}: ${tile.status}`);
    div.title = buildTileTooltip(tile, crop);

    // Icon
    let icon = TILE_ICONS[tile.status] || "⬜";
    if (crop && !crop.is_dead) {
      icon = CROP_ICONS[crop.crop] || icon;
    }

    // Label (crop name or tile coords)
    let label = crop ? `${crop.crop} A${crop.age}` : `${tile.row},${tile.col}`;
    if (tile.locked) { icon = "🔒"; label = "LOCKED"; }

    div.innerHTML = `
      <span class="tile-emoji">${icon}</span>
      <span class="tile-label">${label}</span>
    `;

    grid.appendChild(div);
  });
}

function buildTileTooltip(tile, crop) {
  if (!crop) return `(${tile.row},${tile.col}) ${tile.status}`;
  return (
    `(${tile.row},${tile.col}) ${crop.crop}\n` +
    `Age: ${crop.age} turns\n` +
    `Water: ${crop.water_status}\n` +
    `Fertilized: ${crop.fertilized}\n` +
    `Yield: ${crop.yield_units} units\n` +
    (crop.is_mature ? "✅ MATURE" : `Matures in ~${Math.max(0,48-crop.age)} turns`)
  );
}
