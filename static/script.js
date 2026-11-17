const C = {
  green: "#1DB954",
  greenFill: "rgba(29, 185, 84, 0.12)",
  text: "#F3EEE6",
  muted: "#9B958B",
  grid: "#1F1F1F",
  bg: "#000000",
  pie: ["#1DB954", "#17933F", "#F3EEE6", "#B9B2A6", "#5E5A53"],
};

const fmt = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
const get = async (url) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} failed (${res.status})`);
  return res.json();
};

Chart.defaults.font.family = "'Agrave Pro', 'Helvetica Neue', Arial, sans-serif";
Chart.defaults.font.size = 13;
Chart.defaults.color = C.muted;
Chart.defaults.plugins.tooltip.backgroundColor = "#0B0B0B";
Chart.defaults.plugins.tooltip.borderColor = C.green;
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.titleColor = C.text;
Chart.defaults.plugins.tooltip.bodyColor = C.text;
Chart.defaults.plugins.tooltip.padding = 10;

const charts = {};
let years = [];

function render(key, canvasId, config) {
  if (charts[key]) charts[key].destroy();
  charts[key] = new Chart(document.getElementById(canvasId), config);
}

const scales = (horizontal = false) => ({
  x: { grid: { color: horizontal ? C.grid : "transparent" }, border: { color: C.grid }, ticks: { color: C.muted } },
  y: { grid: { color: horizontal ? "transparent" : C.grid }, border: { color: C.grid }, ticks: { color: C.muted } },
});

async function drawTrend(selectedYear) {
  const d = await get("/api/trend");
  const idx = d.labels.indexOf(selectedYear);
  render("trend", "trendChart", {
    type: "line",
    data: {
      labels: d.labels,
      datasets: [{
        label: "Total value",
        data: d.values,
        borderColor: C.green,
        backgroundColor: C.greenFill,
        fill: true,
        tension: 0.3,
        borderWidth: 3,
        pointRadius: d.labels.map((_, i) => (i === idx ? 8 : 4)),
        pointBackgroundColor: d.labels.map((_, i) => (i === idx ? C.text : C.green)),
        pointBorderColor: C.green,
        pointBorderWidth: d.labels.map((_, i) => (i === idx ? 3 : 1)),
      }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${fmt(c.parsed.y)}` } } },
      scales: scales(false),
    },
  });
}

async function drawCountries(year) {
  const d = await get(`/api/top-countries?year=${year}`);
  render("countries", "countriesChart", {
    type: "bar",
    data: { labels: d.labels, datasets: [{ data: d.values, backgroundColor: C.green, borderRadius: 6, barPercentage: 0.7 }] },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${fmt(c.parsed.x)}` } } },
      scales: scales(true),
    },
  });
}

async function drawCommodities(year) {
  const d = await get(`/api/top-commodities?year=${year}`);
  const total = d.values.reduce((a, b) => a + b, 0);
  render("commodities", "commoditiesChart", {
    type: "doughnut",
    data: { labels: d.labels, datasets: [{ data: d.values, backgroundColor: C.pie, borderColor: C.bg, borderWidth: 3 }] },
    options: {
      maintainAspectRatio: false,
      cutout: "50%",
      plugins: {
        legend: { position: "bottom", labels: { color: C.text, boxWidth: 12, padding: 16 } },
        tooltip: { callbacks: { label: (c) => ` ${fmt(c.parsed)} (${((c.parsed / total) * 100).toFixed(1)}%)` } },
      },
    },
  });
}

async function drawSummary(year) {
  const s = await get(`/api/summary?year=${year}`);
  document.getElementById("kpi-total-label").textContent = `Total value (${year})`;
  document.getElementById("kpi-total").textContent = fmt(s.total_value);
  document.getElementById("kpi-countries").textContent = fmt(s.countries);
  document.getElementById("kpi-commodities").textContent = fmt(s.commodities);
}

async function update(year) {
  document.getElementById("countries-year").textContent = `(${year})`;
  document.getElementById("commodities-year").textContent = `(${year})`;
  await Promise.all([drawSummary(year), drawTrend(year), drawCountries(year), drawCommodities(year)]);
}

async function init() {
  try {
    // Make sure Agrave Pro is ready before Chart.js measures text
    await Promise.all([document.fonts.load("400 13px 'Agrave Pro'"), document.fonts.load("700 13px 'Agrave Pro'")]);
    years = (await get("/api/years")).years;
    const select = document.getElementById("year-select");
    select.innerHTML = years.map((y) => `<option value="${y}">${y}</option>`).join("");
    select.value = years[years.length - 1];
    select.addEventListener("change", (e) => update(Number(e.target.value)));
    await update(years[years.length - 1]);
  } catch (err) {
    console.error(err);
    document.getElementById("note").textContent = "Could not load data. Check that the backend is running and the CSV is in place.";
  }
}

init();
