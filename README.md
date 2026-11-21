# Auto-EDA Engine

An automated Exploratory Data Analysis (Auto-EDA) web application built with **FastAPI**, **Pandas**, and **NumPy** on the backend, and a modern, minimalist dark-mode frontend powered by **Plotly.js**.

Designed around the **Zero Manual Axis Picking** principle: upload any CSV and the heuristic engine automatically profiles the schema, classifies column types, selects optimal dimensions and metrics, detects outliers and Pareto bias, and computes full-fidelity visualizations and executive insights.

---

## Key Highlights

- **Zero Manual Configuration**: No tedious X/Y axis dropdown selection. The backend inspects and ranks columns automatically.
- **Universal CSV Compatibility**: Accepts any tabular CSV dataset (e-commerce, financial, logistics, public health, macro trade).
- **Bundled Demo Dataset**: One-click instant testing with the 184,755-record India Exports dataset (2010–2021).
- **Executive Insights Engine**: Programmatically writes 4 human-readable analytical summaries (Trend trajectory & growth, Category Pareto dominance, Mean vs. Median outlier leverage, Data quality & bias check).
- **Statistical Summary Table**: Deep descriptive statistics across all numeric fields (Count, Mean, Std Dev, Min, Median 50%, Max, Skewness, Missing %).
- **One-Click Data Cleaning**: Toggle automated deduplication and median/category missing value imputation with before/after delta reporting.
- **Dynamic Range Filtering**: Dual-range filtering automatically bound to the dataset's detected time or primary numeric dimension.
- **Minimalist Obsidian Dark Theme**: Designed with `#000000` midnight black, `#0B0B0B` obsidian cards, crisp `#1F1F1F` borders, and `#1DB954` Spotify green accents.

---

## Architecture & Heuristic Profiling

```
                     ┌──────────────────────────┐
                     │     Uploaded Any CSV     │
                     └─────────────┬────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────┐
              │    Automated Heuristic Profiler        │
              └───────┬────────────┬───────────┬───────┘
                      │            │           │
       ┌──────────────┴──────┐     │     ┌─────┴──────────────┐
       │      time_col       │     │     │     metric_cols    │
       │  Years (1900-2100)  │     │     │  Ranked by variance│
       │  or Datetime/String │     │     │  and total volume  │
       └─────────────────────┘     │     └────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │       category_cols         │
                    │  Cardinality (2 to 500)     │
                    │  Ranked for primary/second  │
                    └─────────────────────────────┘
                                   │
                                   ▼
         ┌──────────────────────────────────────────────────┐
         │          Active Aggregation Pipeline             │
         │  Range Filter  •  Deduplication  •  Imputation   │
         └─────────────────────────┬────────────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
    Executive Insights     Statistical Summary      Plotly.js Canvas
    • Trend & Growth       • Count, Mean, Std       • Dynamic Area Trend
    • Pareto Dominance     • Min, Median, Max       • Top 10 Categories
    • Outlier Leverage     • Skewness & Missing %   • Composition Donut
    • Bias Audit                                    • Outliers & Heatmap
```

### Column Classification Heuristics

1. **`time_col`**: Detects ISO datetime strings, timestamp formats, column name tokens (`year`, `date`, `period`, `time`), and integer calendar years ($1900 \le \text{year} \le 2100$).
2. **`id_cols`**: Discovers and filters out primary keys, serial indices, UUIDs, or HS codes (`id`, `code`, `index`, `key`, `uuid`, or uniqueness ratio $> 98\%$).
3. **`metric_cols`**: Continuous numeric columns ranked by variance, non-zero entries, and domain keywords (`value`, `sales`, `revenue`, `price`, `amount`, `profit`) to elect the primary metric.
4. **`category_cols`**: Categorical or string attributes with useful business cardinality ($2 \le \text{unique} \le 500$), ranking primary (e.g. `country`, `region`, `market`) and secondary groupings (e.g. `commodity`, `category`, `segment`).

---

## Visualization & Analytics Modules

| Module | Description | Implementation |
|---|---|---|
| **KPI Monitors** | Summary cards showing Total Rows, Primary Metric Sum & Mean, Unique Categories, Data Completeness %, and Duplicate Count. | Live reactive cards with tabular typography |
| **Executive Insights** | 4 structured analytical findings covering Trend Trajectory, Pareto Dominance, Outlier Leverage, and Data Integrity. | 2-column grid of minimal dark cards |
| **Statistical Summary** | Descriptive parameters: Count, Mean, Std Dev, Min, Median, Max, Skewness, Missing % for all numeric columns. | Minimal dark table with monospace formatting |
| **Time Trend** | Area and spline trajectory over time (or rolling index sequence if no time dimension exists). | Plotly.js line with Spotify green gradient fill |
| **Top 10 Categories** | Horizontal bar chart of top category groups ranked by aggregate volume. Truncated to 28 characters with full names on hover. | Plotly.js horizontal bar with 220px left margin |
| **Sector Composition** | Donut chart displaying the Top 5 groups + aggregated "Other" bucket. | Plotly.js doughnut with 58% cutout |
| **Distribution & Outliers** | Dual-trace composite: frequency histogram + jittered boxplot with parametric skewness interpretation. | Plotly.js multi-row subplot + stat pills |
| **Correlation Matrix** | Pairwise Pearson correlation heatmap across numeric metrics. Automatically hidden when $<2$ numeric dimensions exist. | Plotly.js dark-to-green continuous heatmap |
| **Data Quality & Bias** | Missingness percentages per column + Pareto concentration alerts (flags when top 2 categories absorb $>25\%$ of volume). | Plotly.js bar chart + minimal alert cards |

---

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, Uvicorn, Pandas, NumPy
- **Frontend**: Vanilla HTML5, Modern CSS Grid & Flexbox, Vanilla JavaScript (ES6+)
- **Charting**: Plotly.js (via CDN)
- **Typography**: Inter & JetBrains Mono (via Google Fonts)

---

## Project Structure

```
.
├── Cleaned_India_Export.csv    # Bundled 184k-record demo dataset
├── main.py                     # FastAPI application, profiling engine, endpoints
├── requirements.txt            # Python backend dependencies
├── README.md                   # Project documentation
└── static/
    ├── index.html              # Single-page application markup
    ├── style.css               # Midnight dark design system (zero gimmicks)
    └── script.js               # Reactive state controller & Plotly chart renderers
```

---

## Quickstart

### 1. Prerequisites
Ensure you have **Python 3.9** or higher installed.

### 2. Environment Setup

```bash
# Clone or navigate to the repository
cd /path/to/project

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate       # On Linux/macOS
# .\venv\Scripts\activate      # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch the Server

```bash
uvicorn main:app --reload
```

The application will be live at:
- **Web UI**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## API Reference

### `POST /api/upload`
Accepts a multipart CSV upload. Profiles schema and returns dataset metadata.
- **Request**: `file: UploadFile` (form-data)
- **Response**:
```json
{
  "filename": "dataset.csv",
  "row_count": 184755,
  "col_count": 5,
  "missing_count": 0,
  "duplicate_count": 0,
  "detected_range": {
    "col_name": "year",
    "type": "time_numeric",
    "min": 2010,
    "max": 2021,
    "step": 1
  },
  "available_modules": ["kpis", "insights", "stats_summary", "trend", "distribution", "data_quality", "top_categories", "composition"],
  "profile": {
    "time_col": "year",
    "id_cols": ["HSCode"],
    "primary_metric": "value",
    "primary_category": "country",
    "secondary_category": "Commodity"
  }
}
```

### `POST /api/load-sample`
Instantly loads the bundled 184,755-row India Exports dataset for zero-effort evaluation.

### `POST /api/clean`
Triggers one-click deduplication and missing value imputation (median for numeric, `"Unknown"` for categorical). Returns before/after deltas.

### `POST /api/generate`
Computes ready-to-render visualization payloads for active modules filtered by range.
- **Request Body**:
```json
{
  "modules": ["kpis", "insights", "stats_summary", "trend", "top_categories", "composition", "distribution", "correlation", "data_quality"],
  "range_min": 2012,
  "range_max": 2021,
  "use_cleaned": false
}
```

---

## Design System

| Element | Specification |
|---|---|
| **Background** | `#000000` (Pure Midnight Black) |
| **Card Surfaces** | `#0B0B0B` / `#121212` (Deep Obsidian) |
| **Borders** | `1px solid #1F1F1F` |
| **Primary Accent** | `#1DB954` (Spotify Green), hover: `#1ED760` |
| **Typography** | `Inter` (sans-serif) for body and headings, `JetBrains Mono` for tabular metrics |

---

## License

This project is licensed under the MIT License.
