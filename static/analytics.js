/**
 * analytics.js — Ziply Analytics Page v3 (Phase 4: JWT auth)
 *
 * Reads the short code from the URL path (/analytics/{code}),
 * fetches GET /api/links/{code}/analytics (authenticated), and renders:
 *  - Summary cards (total clicks, short code, last visited)
 *  - Click Trends Chart.js scatter/line chart
 *  - Recent Visits list
 */

'use strict';

// ── Auth guard ───────────────────────────────────────────────────────────────

const TOKEN_KEY   = 'ziply_token';
const USERNAME_KEY = 'ziply_username';

const _token = localStorage.getItem(TOKEN_KEY);
if (!_token) {
  window.location.replace('/login');
}

function authHeaders() {
  return _token ? { 'Authorization': `Bearer ${_token}` } : {};
}

document.addEventListener("DOMContentLoaded", () => {

  // ── Theme (shared with dashboard) ───────────────────────────────────────────

  const html = document.documentElement;
  const themeToggle = document.getElementById("theme-toggle");
  const themeIcon   = themeToggle?.querySelector(".theme-icon");
  const themeLabel  = themeToggle?.querySelector(".theme-label");

  function applyTheme(dark) {
    html.dataset.theme = dark ? "dark" : "light";
    if (themeIcon)  themeIcon.textContent  = dark ? "☀️" : "🌙";
    if (themeLabel) themeLabel.textContent = dark ? "Light" : "Dark";
  }

  let isDark = localStorage.getItem('ziply_theme') === 'dark';
  applyTheme(isDark);

  themeToggle?.addEventListener('click', () => {
    isDark = !isDark;
    localStorage.setItem('ziply_theme', isDark ? 'dark' : 'light');
    applyTheme(isDark);
  });

  // Logout
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    const uname = localStorage.getItem(USERNAME_KEY) || 'User';
    logoutBtn.innerHTML = `<span>⏎</span> ${uname}`;
  }
  logoutBtn?.addEventListener('click', () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    window.location.replace('/login');
  });


  // ── Toast ────────────────────────────────────────────────────────────────────

  const toastEl = document.getElementById("toast");
  let toastTimer = null;

  function showToast(msg, type = "success") {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.className = `toast toast-${type}`;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3200);
  }


  // ── Read code from URL ───────────────────────────────────────────────────────

  const pathParts = window.location.pathname.split("/");
  const code = pathParts[pathParts.length - 1] || "";

  if (!code) {
    document.getElementById("stat-total-clicks").textContent = "Error";
    return;
  }


  // ── Format helpers ───────────────────────────────────────────────────────────

  function fmtDate(isoStr) {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("en-US", {
        month: "numeric", day: "numeric", year: "numeric",
        hour: "numeric", minute: "2-digit", hour12: true,
      });
    } catch { return isoStr; }
  }


  // ── Chart reference ──────────────────────────────────────────────────────────

  let chartInstance = null;

  function renderChart(trends) {
    const canvas = document.getElementById("trends-chart");
    const emptyEl = document.getElementById("chart-empty");

    if (!canvas) return;

    if (!trends || trends.length === 0) {
      canvas.hidden = true;
      if (emptyEl) emptyEl.hidden = false;
      return;
    }

    canvas.hidden = false;
    if (emptyEl) emptyEl.hidden = true;

    // Destroy existing instance before re-creating
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }

    const isDarkNow = html.dataset.theme === "dark";
    const gridColor  = isDarkNow ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
    const labelColor = isDarkNow ? "#8a91b4" : "#6b7280";

    const labels = trends.map(p => {
      const d = new Date(p.timestamp);
      return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
    });
    const values = trends.map(p => p.cumulative);

    chartInstance = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Clicks",
          data: values,
          borderColor: "#f97316",
          backgroundColor: "rgba(249,115,22,0.12)",
          pointBackgroundColor: "#f97316",
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          pointRadius: 6,
          pointHoverRadius: 8,
          tension: 0.35,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#ffffff",
            titleColor: "#1a2035",
            bodyColor: "#f97316",
            borderColor: "#e2e6f0",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              title: (items) => items[0].label,
              label: (item) => `${item.raw} Click${item.raw !== 1 ? "s" : ""}`,
            },
          },
        },
        scales: {
          x: {
            grid:  { color: gridColor },
            ticks: { color: labelColor, font: { size: 11 } },
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: labelColor,
              font: { size: 11 },
              precision: 0,
              stepSize: 1,
            },
            grid: { color: gridColor },
          },
        },
      },
    });
  }


  // ── Recent visits list ───────────────────────────────────────────────────────

  function renderVisits(visits, total) {
    const list    = document.getElementById("visits-list");
    const emptyEl = document.getElementById("visits-empty");
    const badge   = document.getElementById("visit-count-badge");

    if (badge) badge.textContent = `${total} Visit${total !== 1 ? "s" : ""}`;

    if (!list) return;
    list.innerHTML = "";

    if (!visits || visits.length === 0) {
      if (emptyEl) emptyEl.hidden = false;
      return;
    }

    if (emptyEl) emptyEl.hidden = true;

    visits.forEach(v => {
      const row = document.createElement("div");
      row.className = "visit-row";
      row.innerHTML = `
        <div class="visit-left">
          <div class="visit-avatar">👤</div>
          <div>
            <div class="visit-name">Visitor #${v.visitor_number}</div>
            <div class="visit-time">${fmtDate(v.visited_at)}</div>
          </div>
        </div>
        <span class="visit-active-badge">● Active</span>
      `;
      list.appendChild(row);
    });
  }


  // ── Load analytics data ──────────────────────────────────────────────────────

  async function loadAnalytics() {
    try {
      const res = await fetch(`/api/links/${encodeURIComponent(code)}/analytics`, {
        headers: authHeaders(),
      });
      if (!res.ok) {
        document.getElementById("stat-total-clicks").textContent = "—";
        document.getElementById("stat-short-code").textContent   = code;
        document.getElementById("stat-last-visited").textContent = "Not found";
        showToast(`Code "${code}" not found.`, "error");
        return;
      }

      const data = await res.json();

      // Summary cards
      document.getElementById("stat-total-clicks").textContent =
        data.total_clicks;
      document.getElementById("stat-short-code").textContent =
        data.code;
      document.getElementById("stat-last-visited").textContent =
        data.last_visited ? fmtDate(data.last_visited) : "Never";

      const subEl = document.getElementById("stat-last-sub");
      if (subEl) subEl.textContent = data.last_visited
        ? "Latest activity detected"
        : "No visits yet";

      // Chart
      renderChart(data.click_trends);

      // Visits
      renderVisits(data.recent_visits, data.total_clicks);

    } catch (err) {
      showToast("Failed to load analytics.", "error");
    }
  }

  loadAnalytics();

  // Re-render chart if theme changes (colours need updating)
  themeToggle?.addEventListener("click", () => {
    if (chartInstance) {
      // slight delay so CSS vars have applied
      setTimeout(() => {
        chartInstance.options.scales.x.grid.color =
          html.dataset.theme === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
        chartInstance.options.scales.x.ticks.color =
          html.dataset.theme === "dark" ? "#8a91b4" : "#6b7280";
        chartInstance.options.scales.y.grid.color =
          html.dataset.theme === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
        chartInstance.options.scales.y.ticks.color =
          html.dataset.theme === "dark" ? "#8a91b4" : "#6b7280";
        chartInstance.update();
      }, 50);
    }
  });

}); // end DOMContentLoaded
