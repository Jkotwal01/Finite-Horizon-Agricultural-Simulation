/**
 * charts.js — Chart.js wealth chart initialisation and update
 */
"use strict";

let wealthChart = null;
const wealthHistory = [];

function initWealthChart() {
  const ctx = document.getElementById("wealth-chart");
  if (!ctx || wealthChart) return;

  wealthChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Cash ($)",
          data: [],
          borderColor: "#22c55e",
          backgroundColor: "rgba(34,197,94,0.08)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          fill: true,
        },
        {
          label: "Est. Wealth ($)",
          data: [],
          borderColor: "#14b8a6",
          backgroundColor: "rgba(20,184,166,0.05)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          fill: true,
          borderDash: [4, 4],
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: { duration: 150 },
      plugins: {
        legend: {
          labels: {
            color: "#94a3b8",
            font: { family: "Inter", size: 11 },
            boxWidth: 12,
          },
        },
        tooltip: {
          backgroundColor: "rgba(17,24,39,0.95)",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          titleColor: "#f1f5f9",
          bodyColor: "#94a3b8",
          callbacks: {
            label: ctx => ` $${ctx.parsed.y.toFixed(2)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: "#475569",
            font: { size: 10, family: "JetBrains Mono" },
            maxTicksLimit: 10,
          },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
        y: {
          ticks: {
            color: "#475569",
            font: { size: 10, family: "JetBrains Mono" },
            callback: v => `$${v}`,
          },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
      },
    },
  });
}

function updateWealthChart(turn, cash, wealth) {
  if (!wealthChart) return;
  const label = `T${turn}`;
  wealthChart.data.labels.push(label);
  wealthChart.data.datasets[0].data.push(parseFloat(cash.toFixed(2)));
  wealthChart.data.datasets[1].data.push(parseFloat(wealth.toFixed(2)));

  // Keep last 200 points for performance
  if (wealthChart.data.labels.length > 200) {
    wealthChart.data.labels.shift();
    wealthChart.data.datasets.forEach(d => d.data.shift());
  }

  wealthChart.update("none"); // skip animation for speed
}
