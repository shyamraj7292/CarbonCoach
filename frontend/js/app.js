const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const photoInput = document.getElementById("photo-input");
const onboardForm = document.getElementById("onboard-form");
const countrySelect = document.getElementById("country-select");
const goalInput = document.getElementById("goal-input");
const goalPill = document.getElementById("goal-pill");

let trendChart, categoryChart;

const CATEGORY_COLORS = {
  transport: "#34d399",
  food: "#f59e0b",
  energy: "#60a5fa",
  shopping: "#a78bfa",
  waste: "#f87171",
};

function addMessage(text, role, actions) {
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  const p = document.createElement("p");
  p.textContent = text;
  div.appendChild(p);

  if (actions && actions.length) {
    const box = document.createElement("div");
    box.className = "msg-actions";
    actions.forEach((a) => {
      if (a.tool === "log_activity" && a.result && a.result.co2e_kg !== undefined) {
        const line = document.createElement("div");
        line.className = "action-line";
        line.innerHTML = `<span>Logged: ${a.result.label} (${a.result.quantity} ${a.result.unit})</span><span>${a.result.co2e_kg} kg CO2e</span>`;
        box.appendChild(line);
      }
    });
    if (box.children.length) div.appendChild(box);
  }

  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function sendMessage(message) {
  addMessage(message, "user");
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const data = await res.json();
  addMessage(data.reply, "bot", data.actions);
  await refreshDashboard();
}

async function sendPhoto(file) {
  addMessage(`📷 ${file.name}`, "user");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/photo", { method: "POST", body: form });
  const data = await res.json();
  addMessage(data.reply, "bot", data.actions);
  await refreshDashboard();
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  chatInput.value = "";
  sendMessage(message);
});

photoInput.addEventListener("change", () => {
  const file = photoInput.files[0];
  if (file) sendPhoto(file);
  photoInput.value = "";
});

onboardForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await fetch("/api/onboard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      country: countrySelect.value,
      goal_annual_kg: Number(goalInput.value),
    }),
  });
  await refreshDashboard();
});

async function refreshDashboard() {
  const [summaryRes, historyRes, insightsRes, profileRes] = await Promise.all([
    fetch("/api/dashboard/summary"),
    fetch("/api/dashboard/history?days=14"),
    fetch("/api/insights"),
    fetch("/api/onboard"),
  ]);
  const summary = await summaryRes.json();
  const history = await historyRes.json();
  const insights = await insightsRes.json();
  const profile = await profileRes.json();

  document.getElementById("today-kg").textContent = summary.today_kg;
  document.getElementById("week-kg").textContent = summary.week_kg;
  document.getElementById("month-kg").textContent = summary.month_kg;

  const cmp = summary.comparison;
  const pct = cmp.vs_country_average_pct;
  const direction = pct <= 0 ? "below" : "above";
  document.getElementById("comparison-text").textContent =
    `Annualized at ${cmp.annual_kg} kg CO2e/yr — ${Math.abs(pct)}% ${direction} the ${cmp.country} average (${cmp.country_average_annual_kg} kg/yr).`;

  document.getElementById("insight-text").textContent = insights.summary;

  countrySelect.value = profile.country;
  goalInput.value = profile.goal_annual_kg;
  goalPill.textContent = `Goal: ${profile.goal_annual_kg} kg CO2e / yr`;

  renderTrendChart(history.series);
  renderCategoryChart(summary.by_category_month);
}

function renderTrendChart(series) {
  const ctx = document.getElementById("trend-chart");
  const labels = series.map((s) => s.date.slice(5));
  const data = series.map((s) => s.co2e_kg);

  if (trendChart) {
    trendChart.data.labels = labels;
    trendChart.data.datasets[0].data = data;
    trendChart.update();
    return;
  }

  trendChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "kg CO2e",
        data,
        borderColor: "#34d399",
        backgroundColor: "rgba(52, 211, 153, 0.15)",
        fill: true,
        tension: 0.3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#9aa3b2" }, grid: { color: "#2a2f3a" } },
        y: { ticks: { color: "#9aa3b2" }, grid: { color: "#2a2f3a" }, beginAtZero: true },
      },
    },
  });
}

function renderCategoryChart(byCategory) {
  const ctx = document.getElementById("category-chart");
  const labels = Object.keys(byCategory);
  const data = Object.values(byCategory);
  const colors = labels.map((l) => CATEGORY_COLORS[l] || "#9aa3b2");

  if (categoryChart) {
    categoryChart.data.labels = labels;
    categoryChart.data.datasets[0].data = data;
    categoryChart.data.datasets[0].backgroundColor = colors;
    categoryChart.update();
    return;
  }

  categoryChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { color: "#e6e9ef" } } },
    },
  });
}

refreshDashboard();
