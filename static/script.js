/**
 * Auto-EDA Engine - Frontend Controller
 * Interacts with FastAPI backend:
 *   - POST /api/upload
 *   - POST /api/load-sample
 *   - POST /api/clean
 *   - POST /api/generate
 * Zero manual axis picking: displays automated heuristics, executive insights,
 * descriptive statistics, and Plotly.js charts.
 */

// ---------------------------------------------------------------------------
// 1. Application State
// ---------------------------------------------------------------------------
const state = {
  isLoaded: false,
  useCleaned: false,
  metadata: null,
  activeModules: new Set([
    "kpis",
    "insights",
    "stats_summary",
    "trend",
    "top_categories",
    "composition",
    "distribution",
    "correlation",
    "data_quality",
  ]),
  detectedRange: null,
  currentRange: { min: null, max: null },
  cleanStats: null,
};

let debounceTimer = null;

// ---------------------------------------------------------------------------
// 2. Formatting Helpers
// ---------------------------------------------------------------------------
function formatNumber(num, maxDecimals = 2) {
  if (num === null || num === undefined || isNaN(num)) return "–";
  return Number(num).toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDecimals,
  });
}

function formatCurrencyOrMetric(val) {
  if (val === null || val === undefined || isNaN(val)) return "–";
  const n = Number(val);
  const absN = Math.abs(n);
  if (absN >= 1e9) {
    return `${(n / 1e9).toFixed(2)}B`;
  }
  if (absN >= 1e6) {
    return `${(n / 1e6).toFixed(2)}M`;
  }
  if (absN >= 1e3) {
    return `${(n / 1e3).toFixed(1)}K`;
  }
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

// ---------------------------------------------------------------------------
// 3. Plotly Theme Configuration (Clean, Dark, Minimal)
// ---------------------------------------------------------------------------
const PLOT_THEME = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: {
    family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    color: "#8E8E93",
    size: 11,
  },
  margin: { l: 50, r: 20, t: 20, b: 36 },
  xaxis: {
    gridcolor: "#1F1F1F",
    linecolor: "#1F1F1F",
    tickcolor: "#1F1F1F",
    tickfont: { color: "#8E8E93", size: 10 },
    zerolinecolor: "#1F1F1F",
  },
  yaxis: {
    gridcolor: "#1F1F1F",
    linecolor: "#1F1F1F",
    tickcolor: "#1F1F1F",
    tickfont: { color: "#8E8E93", size: 10 },
    zerolinecolor: "#1F1F1F",
  },
  hoverlabel: {
    bgcolor: "#121212",
    bordercolor: "#1DB954",
    font: { family: "'Inter', sans-serif", color: "#F5F5F5", size: 12 },
  },
};

const PLOT_CONFIG = {
  responsive: true,
  displayModeBar: false,
};

// ---------------------------------------------------------------------------
// 4. API Calls
// ---------------------------------------------------------------------------
function showLoading(msg = "Computing analysis...") {
  const el = document.getElementById("loadingOverlay");
  const txt = document.getElementById("spinnerText");
  if (txt) txt.textContent = msg;
  if (el) el.style.display = "flex";
}

function hideLoading() {
  const el = document.getElementById("loadingOverlay");
  if (el) el.style.display = "none";
}

async function apiPost(url, body = null, isFormData = false) {
  const opts = { method: "POST" };
  if (body) {
    if (isFormData) {
      opts.body = body;
    } else {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
  }

  const res = await fetch(url, opts);
  if (!res.ok) {
    let errDetail = "API error";
    try {
      const errJson = await res.json();
      errDetail = errJson.detail || errDetail;
    } catch (e) {}
    throw new Error(errDetail);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// 5. App Initialization & Event Listeners
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  setupUploadHandlers();
  setupCleanToggle();
  setupModuleChips();
});

function setupUploadHandlers() {
  const fileInput = document.getElementById("fileInput");
  const btnUpload = document.getElementById("btnUpload");
  const btnEmptyUpload = document.getElementById("btnEmptyUpload");
  const btnLoadSample = document.getElementById("btnLoadSample");
  const btnEmptySample = document.getElementById("btnEmptySample");
  const dropzone = document.getElementById("dropzone");

  if (btnUpload && fileInput) btnUpload.addEventListener("click", () => fileInput.click());
  if (btnEmptyUpload && fileInput) btnEmptyUpload.addEventListener("click", () => fileInput.click());

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
      }
    });
  }

  if (btnLoadSample) btnLoadSample.addEventListener("click", handleLoadSample);
  if (btnEmptySample) btnEmptySample.addEventListener("click", handleLoadSample);

  if (dropzone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove("dragover");
      });
    });

    dropzone.addEventListener("drop", (e) => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const file = e.dataTransfer.files[0];
        if (file.name.toLowerCase().endsWith(".csv")) {
          handleFileUpload(file);
        } else {
          alert("Please upload a CSV (.csv) file.");
        }
      }
    });
  }

  const btnCloseBanner = document.getElementById("btnCloseCleanBanner");
  if (btnCloseBanner) {
    btnCloseBanner.addEventListener("click", () => {
      const banner = document.getElementById("cleanBanner");
      if (banner) banner.style.display = "none";
    });
  }
}

async function handleFileUpload(file) {
  showLoading(`Analyzing ${file.name}...`);
  try {
    const formData = new FormData();
    formData.append("file", file);
    const meta = await apiPost("/api/upload", formData, true);
    onDatasetLoaded(meta);
  } catch (err) {
    alert(`Upload failed: ${err.message}`);
  } finally {
    hideLoading();
  }
}

async function handleLoadSample() {
  showLoading("Loading sample dataset (184,755 records)...");
  try {
    const meta = await apiPost("/api/load-sample");
    onDatasetLoaded(meta);
  } catch (err) {
    alert(`Failed to load sample dataset: ${err.message}`);
  } finally {
    hideLoading();
  }
}

// ---------------------------------------------------------------------------
// 6. Dataset Loaded Handler & UI Transition
// ---------------------------------------------------------------------------
function onDatasetLoaded(meta) {
  state.isLoaded = true;
  state.metadata = meta;
  state.cleanStats = meta.clean_stats;
  state.detectedRange = meta.detected_range;

  document.getElementById("emptyState").style.display = "none";
  document.getElementById("moduleBar").style.display = "block";
  document.getElementById("dashboardView").style.display = "block";

  const prof = meta.profile;
  const timeDesc = prof.time_col ? `Time [${prof.time_col}]` : "No Time Col";
  const metricDesc = `Metric [${prof.primary_metric}]`;
  const catDesc = prof.primary_category ? `Category [${prof.primary_category}]` : "Single Dimension";
  document.getElementById("profileSummaryText").textContent =
    `${timeDesc} · ${metricDesc} · ${catDesc} (${formatNumber(meta.row_count, 0)} rows)`;

  setupRangeFilter(meta.detected_range);

  // Check numeric column count for Correlation Matrix handling
  const numMetrics = (prof.all_metrics || []).length;
  const hasCorrelation = meta.available_modules.includes("correlation") && numMetrics >= 2;

  const avail = new Set(meta.available_modules);
  if (!hasCorrelation) {
    avail.delete("correlation");
    state.activeModules.delete("correlation");
    const chipCorr = document.getElementById("chipCorrelation");
    if (chipCorr) {
      chipCorr.style.display = "none";
      chipCorr.classList.remove("active");
    }
    const cardCorr = document.getElementById("cardCorrelation");
    if (cardCorr) cardCorr.style.display = "none";
  }

  document.querySelectorAll(".chip").forEach((chip) => {
    const mod = chip.dataset.module;
    if (mod === "correlation" && !hasCorrelation) {
      chip.style.display = "none";
      return;
    }

    if (avail.has(mod)) {
      chip.style.display = "inline-flex";
      chip.classList.add("active");
      state.activeModules.add(mod);
      toggleCardVisibility(mod, true);
    } else {
      chip.style.display = "none";
      chip.classList.remove("active");
      state.activeModules.delete(mod);
      toggleCardVisibility(mod, false);
    }
  });

  generateVisualizations();
}

// ---------------------------------------------------------------------------
// 7. Range Filter Control
// ---------------------------------------------------------------------------
function setupRangeFilter(rangeInfo) {
  const box = document.getElementById("rangeControlBox");
  if (!rangeInfo || rangeInfo.min === undefined || rangeInfo.max === undefined) {
    if (box) box.style.display = "none";
    return;
  }

  box.style.display = "flex";
  document.getElementById("rangeLabel").textContent = `Range [${rangeInfo.col_name}]`;

  const sliderMin = document.getElementById("rangeSliderMin");
  const sliderMax = document.getElementById("rangeSliderMax");

  const minVal = Number(rangeInfo.min);
  const maxVal = Number(rangeInfo.max);
  const stepVal = Number(rangeInfo.step) || 1;

  sliderMin.min = minVal;
  sliderMin.max = maxVal;
  sliderMin.step = stepVal;
  sliderMin.value = minVal;

  sliderMax.min = minVal;
  sliderMax.max = maxVal;
  sliderMax.step = stepVal;
  sliderMax.value = maxVal;

  state.currentRange = { min: minVal, max: maxVal };
  updateRangeDisplay(minVal, maxVal);

  sliderMin.oninput = (e) => {
    let vMin = Number(e.target.value);
    let vMax = Number(sliderMax.value);
    if (vMin > vMax) {
      vMin = vMax;
      sliderMin.value = vMin;
    }
    state.currentRange.min = vMin;
    updateRangeDisplay(vMin, vMax);
    triggerDebouncedGenerate();
  };

  sliderMax.oninput = (e) => {
    let vMin = Number(sliderMin.value);
    let vMax = Number(e.target.value);
    if (vMax < vMin) {
      vMax = vMin;
      sliderMax.value = vMax;
    }
    state.currentRange.max = vMax;
    updateRangeDisplay(vMin, vMax);
    triggerDebouncedGenerate();
  };
}

function updateRangeDisplay(min, max) {
  const disp = document.getElementById("rangeValDisplay");
  if (!disp) return;
  if (state.detectedRange && state.detectedRange.type === "time_numeric") {
    disp.textContent = `${min} – ${max}`;
  } else {
    disp.textContent = `${formatCurrencyOrMetric(min)} – ${formatCurrencyOrMetric(max)}`;
  }
}

function triggerDebouncedGenerate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    generateVisualizations(false);
  }, 180);
}

// ---------------------------------------------------------------------------
// 8. Auto-Clean Toggle
// ---------------------------------------------------------------------------
function setupCleanToggle() {
  const toggle = document.getElementById("cleanToggle");
  const pill = document.getElementById("cleanStatusPill");
  const banner = document.getElementById("cleanBanner");
  const bannerText = document.getElementById("cleanBannerText");

  if (!toggle) return;

  toggle.addEventListener("change", async (e) => {
    state.useCleaned = e.target.checked;
    if (state.useCleaned) {
      pill.textContent = "Cleaned";
      pill.classList.add("active");

      if (!state.cleanStats && state.isLoaded) {
        try {
          state.cleanStats = await apiPost("/api/clean");
        } catch (err) {
          console.error("Clean error:", err);
        }
      }

      if (state.cleanStats && banner && bannerText) {
        const s = state.cleanStats;
        bannerText.textContent = `Removed ${s.dropped_duplicates} duplicate rows; imputed ${s.imputed_numeric_count} numeric values and ${s.imputed_category_count} category values.`;
        banner.style.display = "flex";
      }
    } else {
      pill.textContent = "Raw";
      pill.classList.remove("active");
      if (banner) banner.style.display = "none";
    }

    if (state.isLoaded) {
      generateVisualizations();
    }
  });
}

// ---------------------------------------------------------------------------
// 9. Module Chips Selector
// ---------------------------------------------------------------------------
function setupModuleChips() {
  const chips = document.querySelectorAll(".chip");
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const mod = chip.dataset.module;
      if (state.activeModules.has(mod)) {
        state.activeModules.delete(mod);
        chip.classList.remove("active");
      } else {
        state.activeModules.add(mod);
        chip.classList.add("active");
      }
      toggleCardVisibility(mod, state.activeModules.has(mod));
      generateVisualizations(false);
    });
  });
}

function toggleCardVisibility(moduleKey, isVisible) {
  const mapping = {
    kpis: "kpiStrip",
    insights: "cardInsights",
    stats_summary: "cardStatsSummary",
    trend: "cardTrend",
    top_categories: "cardTopCategories",
    composition: "cardComposition",
    distribution: "cardDistribution",
    correlation: "cardCorrelation",
    data_quality: "cardDataQuality",
  };

  const id = mapping[moduleKey];
  if (id) {
    const el = document.getElementById(id);
    if (el) el.style.display = isVisible ? "" : "none";
  }
}

// ---------------------------------------------------------------------------
// 10. Core Generation & Chart Renderers
// ---------------------------------------------------------------------------
async function generateVisualizations(showSpinner = true) {
  if (!state.isLoaded) return;
  if (showSpinner) showLoading("Updating analysis...");

  try {
    const payload = {
      modules: Array.from(state.activeModules),
      range_min: state.currentRange.min,
      range_max: state.currentRange.max,
      use_cleaned: state.useCleaned,
    };

    const res = await apiPost("/api/generate", payload);

    if (res.kpis) renderKPIs(res.kpis);
    if (res.insights) renderInsights(res.insights);
    if (res.stats_summary) renderStatsSummary(res.stats_summary);
    if (res.trend) renderTrend(res.trend);
    if (res.top_categories) renderTopCategories(res.top_categories);
    if (res.composition) renderComposition(res.composition);
    if (res.distribution) renderDistribution(res.distribution);
    if (res.correlation) renderCorrelation(res.correlation);
    if (res.data_quality) renderDataQuality(res.data_quality);

  } catch (err) {
    console.error("Generation error:", err);
  } finally {
    if (showSpinner) hideLoading();
  }
}

// --- KPI Strip Renderer ---
function renderKPIs(kpis) {
  document.getElementById("kpiRows").textContent = formatNumber(kpis.total_rows, 0);
  document.getElementById("kpiMetricSum").textContent = formatCurrencyOrMetric(kpis.metric_sum);
  document.getElementById("kpiMetricMeanSub").textContent = `Mean: ${formatCurrencyOrMetric(kpis.metric_mean)}`;
  document.getElementById("kpiMetricLabel").textContent = `Total ${kpis.metric_name}`;
  document.getElementById("kpiCatUnique").textContent = formatNumber(kpis.top_category_unique, 0);
  document.getElementById("kpiCatNameSub").textContent = `${kpis.category_name} groups`;
  document.getElementById("kpiCompleteness").textContent = `${kpis.completeness_pct}%`;
  document.getElementById("kpiDuplicates").textContent = formatNumber(kpis.duplicate_count, 0);
  document.getElementById("kpiReason2").textContent = kpis.metric_name;
  document.getElementById("kpiReason3").textContent = kpis.category_name;
}

// --- Executive Insights Renderer (2-Column Minimal Dark Cards, Zero Emojis) ---
function renderInsights(data) {
  const container = document.getElementById("insightsGrid");
  const reasonEl = document.getElementById("insightsReason");
  if (!container) return;

  if (reasonEl) reasonEl.textContent = data.auto_reason || "Synthesized Macro Findings";
  container.innerHTML = "";

  (data.items || []).forEach((item) => {
    const card = document.createElement("div");
    card.className = "insight-card";

    const top = document.createElement("div");
    top.className = "insight-card-top";

    const title = document.createElement("h4");
    title.className = "insight-card-title";
    title.textContent = item.title;

    const tag = document.createElement("span");
    tag.className = "insight-card-tag";
    tag.textContent = (item.category || "Insight").toUpperCase();

    top.appendChild(title);
    top.appendChild(tag);

    const text = document.createElement("p");
    text.className = "insight-card-text";
    text.textContent = item.text;

    card.appendChild(top);
    card.appendChild(text);
    container.appendChild(card);
  });
}

// --- Statistical Summary Table Renderer (df.describe() across all numeric dimensions) ---
function renderStatsSummary(data) {
  const tbody = document.getElementById("statsSummaryBody");
  const reasonEl = document.getElementById("statsSummaryReason");
  if (!tbody) return;

  if (reasonEl) reasonEl.textContent = data.auto_reason || "Descriptive Parameters";
  tbody.innerHTML = "";

  (data.rows || []).forEach((row) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td class="col-name">${row.column}</td>
      <td class="col-num">${formatNumber(row.count, 0)}</td>
      <td class="col-num">${formatNumber(row.mean, 2)}</td>
      <td class="col-num">${formatNumber(row.std, 2)}</td>
      <td class="col-num">${formatNumber(row.min, 2)}</td>
      <td class="col-num">${formatNumber(row.median, 2)}</td>
      <td class="col-num">${formatNumber(row.max, 2)}</td>
      <td class="col-num">${formatNumber(row.skewness, 2)}</td>
      <td class="col-num">${row.missing_pct}%</td>
    `;
    tbody.appendChild(tr);
  });
}

// --- Trend Chart Renderer ---
function renderTrend(data) {
  const container = document.getElementById("plotTrend");
  if (!container) return;

  document.getElementById("trendTitle").textContent = `${data.y_label} over ${data.x_label}`;
  document.getElementById("trendReason").textContent = data.auto_reason;

  const trace = {
    x: data.x,
    y: data.y,
    type: "scatter",
    mode: "lines+markers",
    fill: "tozeroy",
    fillcolor: "rgba(29, 185, 84, 0.1)",
    line: { color: "#1DB954", width: 2.5, shape: "spline" },
    marker: { color: "#1DB954", size: 5, line: { color: "#000000", width: 1.5 } },
    hovertemplate: `<b>%{x}</b><br>Volume: %{y:,.2f}<extra></extra>`,
  };

  const layout = {
    ...PLOT_THEME,
    xaxis: { ...PLOT_THEME.xaxis, title: { text: data.x_label, font: { size: 10, color: "#8E8E93" } } },
    yaxis: { ...PLOT_THEME.yaxis, title: { text: data.y_label, font: { size: 10, color: "#8E8E93" } } },
  };

  Plotly.newPlot(container, [trace], layout, PLOT_CONFIG);
}

// --- Top Categories Renderer (Truncate to 28 chars with ... on y-axis, full name on hover, 220px left margin) ---
function renderTopCategories(data) {
  const container = document.getElementById("plotTopCategories");
  if (!container) return;

  document.getElementById("topCatTitle").textContent = `Top 10 ${data.category_col} by ${data.metric_col}`;
  document.getElementById("topCatReason").textContent = data.auto_reason;

  // Truncate labels for Y-axis (max 28 chars)
  const displayLabels = (data.categories || []).map((cat) => {
    const s = String(cat);
    return s.length > 28 ? s.substring(0, 25) + "..." : s;
  });

  const fullLabels = data.full_categories || data.categories || [];

  const trace = {
    x: data.values,
    y: displayLabels,
    customdata: fullLabels,
    type: "bar",
    orientation: "h",
    marker: {
      color: data.values,
      colorscale: [
        [0, "#0e3a1f"],
        [0.5, "#147a38"],
        [1, "#1DB954"],
      ],
      line: { color: "rgba(255,255,255,0.06)", width: 1 },
    },
    hovertemplate: `<b>%{customdata}</b><br>Aggregate: %{x:,.2f}<extra></extra>`,
  };

  const layout = {
    ...PLOT_THEME,
    margin: { l: 220, r: 25, t: 15, b: 35 },
    xaxis: { ...PLOT_THEME.xaxis, title: { text: data.metric_col, font: { size: 10 } } },
    yaxis: {
      ...PLOT_THEME.yaxis,
      automargin: true,
      tickfont: { size: 10, color: "#F5F5F5" },
    },
  };

  Plotly.newPlot(container, [trace], layout, PLOT_CONFIG);
}

// --- Composition Doughnut Renderer ---
function renderComposition(data) {
  const container = document.getElementById("plotComposition");
  if (!container) return;

  document.getElementById("compTitle").textContent = `${data.category_col} Composition Breakdown`;
  document.getElementById("compReason").textContent = data.auto_reason;

  const trace = {
    labels: data.labels,
    customdata: data.full_labels || data.labels,
    values: data.values,
    type: "pie",
    hole: 0.58,
    marker: {
      colors: ["#1DB954", "#1ed760", "#17933f", "#34d399", "#0d5c27", "#4b5563"],
      line: { color: "#000000", width: 2 },
    },
    textinfo: "label+percent",
    textposition: "inside",
    insidetextfont: { color: "#FFFFFF", size: 10 },
    hovertemplate: `<b>%{customdata}</b><br>Value: %{value:,.2f} (%{percent})<extra></extra>`,
  };

  const layout = {
    ...PLOT_THEME,
    showlegend: true,
    legend: {
      font: { color: "#8E8E93", size: 10 },
      orientation: "h",
      x: 0,
      y: -0.15,
    },
    margin: { l: 20, r: 20, t: 10, b: 50 },
  };

  Plotly.newPlot(container, [trace], layout, PLOT_CONFIG);
}

// --- Distribution & Outliers Renderer ---
function renderDistribution(data) {
  const container = document.getElementById("plotDistribution");
  if (!container) return;

  document.getElementById("distReason").textContent = data.auto_reason;

  if (data.stats) {
    const s = data.stats;
    document.getElementById("pillMean").textContent = `Mean: ${formatCurrencyOrMetric(s.mean)}`;
    document.getElementById("pillMedian").textContent = `Median: ${formatCurrencyOrMetric(s.median)}`;
    document.getElementById("pillStd").textContent = `Std: ${formatCurrencyOrMetric(s.std)}`;
    document.getElementById("pillSkew").textContent = `Skew: ${s.skew}`;
    document.getElementById("skewDescText").textContent = s.skew_interpretation || "";
  }

  const histTrace = {
    x: data.hist_x,
    y: data.hist_y,
    type: "bar",
    name: "Frequency",
    marker: {
      color: "rgba(29, 185, 84, 0.4)",
      line: { color: "#1DB954", width: 1 },
    },
    hovertemplate: `Bin Mid: %{x:,.2f}<br>Count: %{y:,}<extra></extra>`,
  };

  const boxTrace = {
    x: data.sample_points || [],
    type: "box",
    name: "Outlier Spread",
    boxpoints: "outliers",
    jitter: 0.3,
    pointpos: -1.8,
    marker: { color: "#1DB954", size: 3.5 },
    line: { color: "#1ED760", width: 1.5 },
    yaxis: "y2",
  };

  const layout = {
    ...PLOT_THEME,
    showlegend: false,
    grid: { rows: 2, columns: 1, pattern: "independent" },
    xaxis: { ...PLOT_THEME.xaxis },
    yaxis: { ...PLOT_THEME.yaxis, title: { text: "Frequency", font: { size: 9 } } },
    yaxis2: { ...PLOT_THEME.yaxis, showticklabels: false },
    margin: { l: 45, r: 20, t: 15, b: 35 },
  };

  Plotly.newPlot(container, [histTrace, boxTrace], layout, PLOT_CONFIG);
}

// --- Correlation Heatmap Renderer (Only rendered if >= 2 numeric cols) ---
function renderCorrelation(data) {
  const container = document.getElementById("plotCorrelation");
  const card = document.getElementById("cardCorrelation");
  if (!container) return;

  if (!data || data.available === false || !data.columns || data.columns.length < 2) {
    if (card) card.style.display = "none";
    return;
  }

  if (card && state.activeModules.has("correlation")) {
    card.style.display = "";
  }

  document.getElementById("corrReason").textContent = data.auto_reason;

  const trace = {
    z: data.z,
    x: data.columns,
    y: data.columns,
    type: "heatmap",
    colorscale: [
      [0, "#000000"],
      [0.5, "#0e3a1f"],
      [1, "#1DB954"],
    ],
    zmin: -1,
    zmax: 1,
    showscale: true,
    colorbar: {
      tickcolor: "#1F1F1F",
      tickfont: { color: "#8E8E93", size: 9 },
      thickness: 10,
    },
    hovertemplate: `%{x} vs %{y}<br>Correlation: %{z:.2f}<extra></extra>`,
  };

  const layout = {
    ...PLOT_THEME,
    margin: { l: 80, r: 40, t: 20, b: 60 },
  };

  Plotly.newPlot(container, [trace], layout, PLOT_CONFIG);
}

// --- Data Quality & Bias Renderer (Zero Emojis, Minimal Dark Alert Cards) ---
function renderDataQuality(data) {
  const container = document.getElementById("plotQuality");
  const alertsList = document.getElementById("alertsList");
  if (!container || !alertsList) return;

  document.getElementById("qualityReason").textContent = data.auto_reason;

  const trace = {
    x: data.columns,
    y: data.missing_pcts,
    type: "bar",
    marker: {
      color: data.missing_pcts.map((pct) => (pct > 20 ? "#EF4444" : pct > 5 ? "#EAB308" : "#1DB954")),
      line: { color: "rgba(255,255,255,0.06)", width: 1 },
    },
    hovertemplate: `<b>%{x}</b><br>Missing: %{y:.2f}%<extra></extra>`,
  };

  const layout = {
    ...PLOT_THEME,
    yaxis: {
      ...PLOT_THEME.yaxis,
      title: { text: "Missing %", font: { size: 9 } },
      range: [0, Math.max(10, Math.max(...data.missing_pcts, 5) * 1.2)],
    },
    margin: { l: 45, r: 15, t: 15, b: 45 },
  };

  Plotly.newPlot(container, [trace], layout, PLOT_CONFIG);

  alertsList.innerHTML = "";
  if (data.bias_warnings && data.bias_warnings.length > 0) {
    data.bias_warnings.forEach((warn) => {
      const cleanWarn = warn.replace(/[🚨⚡⚠️ℹ️✅]/g, "").trim();
      const item = document.createElement("div");
      item.className = "alert-item";
      if (cleanWarn.toLowerCase().includes("alert") || cleanWarn.toLowerCase().includes("danger")) {
        item.classList.add("alert-danger");
      } else if (cleanWarn.toLowerCase().includes("concentration") || cleanWarn.toLowerCase().includes("incompleteness")) {
        item.classList.add("alert-warning");
      }
      item.textContent = cleanWarn;
      alertsList.appendChild(item);
    });
  }
}

// ---------------------------------------------------------------------------
// 11. Window Resize Responsive Handler
// ---------------------------------------------------------------------------
window.addEventListener("resize", () => {
  const plotIds = [
    "plotTrend",
    "plotTopCategories",
    "plotComposition",
    "plotDistribution",
    "plotCorrelation",
    "plotQuality",
  ];
  plotIds.forEach((id) => {
    const el = document.getElementById(id);
    if (el && el.data) {
      Plotly.Plots.resize(el);
    }
  });
});
