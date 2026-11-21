"""
Automated Exploratory Data Analysis (Auto-EDA) Web Application
FastAPI + Pandas + NumPy Backend
Zero manual axis picking: smart heuristics automatically profile,
classify, and aggregate datasets.
"""

from pathlib import Path
from typing import List, Optional, Any, Dict
import io
import re
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
SAMPLE_FILE = BASE_DIR / "Cleaned_India_Export.csv"

app = FastAPI(title="Auto-EDA Engine", description="Automated Zero-Configuration Data Profiler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# In-Memory Dataset Store
# ---------------------------------------------------------------------------
class DatasetManager:
    def __init__(self):
        self.raw_df: Optional[pd.DataFrame] = None
        self.cleaned_df: Optional[pd.DataFrame] = None
        self.filename: str = ""
        self.profile: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self.clean_stats: Optional[Dict[str, Any]] = None

    def reset(self):
        self.raw_df = None
        self.cleaned_df = None
        self.filename = ""
        self.profile = {}
        self.metadata = {}
        self.clean_stats = None


dataset_state = DatasetManager()


# ---------------------------------------------------------------------------
# JSON Sanitizer Helper (converts NaN, inf, np types to pure JSON serializable)
# ---------------------------------------------------------------------------
def sanitize(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    if isinstance(val, dict):
        return {str(k): sanitize(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [sanitize(v) for v in val]
    return val


# ---------------------------------------------------------------------------
# Smart Heuristics Profiler
# ---------------------------------------------------------------------------
def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Classifies DataFrame columns into:
    - time_col: datetime or integer year [1900-2100] or column name matching time patterns
    - id_cols: identifier/code columns (e.g. HSCode, Index, ID, 100% uniqueness)
    - metric_cols: continuous numeric variables ranked by variance / sum / volume
    - category_cols: categorical columns with cardinality between 2 and 500
    """
    total_rows = len(df)
    id_cols = []
    time_candidates = []
    metric_candidates = []
    category_candidates = []

    # First pass: identify ID columns and time candidates
    for col in df.columns:
        col_str = str(col).strip()
        col_lower = col_str.lower()
        nunique = df[col].nunique(dropna=True)

        # Heuristic 1: ID / Key detection
        id_pattern = r"(^|\b|_)(id|code|index|key|uuid|pk|s_no|sno|hscode|serial)(\b|_|$)"
        if re.search(id_pattern, col_lower):
            id_cols.append(col)
            continue
        if total_rows > 50 and (nunique / total_rows) > 0.98:
            id_cols.append(col)
            continue

        # Heuristic 2: Time / Date detection
        is_time = False
        time_name_pattern = r"(^|\b|_)(year|date|datetime|timestamp|time|period|yr|dt|day|month)(\b|_|$)"
        if re.search(time_name_pattern, col_lower):
            is_time = True
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            is_time = True
        elif pd.api.types.is_integer_dtype(df[col]) or pd.api.types.is_float_dtype(df[col]):
            non_nulls = df[col].dropna()
            if len(non_nulls) > 0:
                c_min = non_nulls.min()
                c_max = non_nulls.max()
                if 1900 <= c_min and c_max <= 2100 and nunique >= 2:
                    is_time = True
        elif df[col].dtype == object or isinstance(df[col].dtype, pd.StringDtype):
            sample = df[col].dropna().head(20)
            if len(sample) >= 3:
                try:
                    parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().sum() / len(sample) >= 0.8:
                        is_time = True
                except Exception:
                    pass

        if is_time:
            time_candidates.append(col)
            continue

        # Heuristic 3: Numeric Metrics
        if pd.api.types.is_numeric_dtype(df[col]):
            if nunique > 1:
                metric_candidates.append(col)
            continue

        # Heuristic 4: Categorical columns (cardinality 2 - 500)
        if nunique >= 2 and nunique <= 500:
            category_candidates.append(col)

    # Secondary check: if integer column was placed in category candidates but looks like metric
    for col in list(category_candidates):
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].nunique() > 10:
            if col not in metric_candidates:
                metric_candidates.append(col)

    # Rank Time column
    time_col = None
    if time_candidates:
        def time_score(c):
            cl = str(c).lower()
            if "year" in cl or "yr" in cl:
                return 100
            if "date" in cl or "dt" in cl:
                return 90
            if "time" in cl or "period" in cl:
                return 80
            return 50
        time_candidates.sort(key=time_score, reverse=True)
        time_col = time_candidates[0]

    # Rank Metric columns
    primary_metric = None
    if metric_candidates:
        def metric_score(c):
            score = 0.0
            cl = str(c).lower()
            if any(k in cl for k in ["value", "amount", "total", "sales", "revenue", "price", "profit", "cost", "sum", "vol", "export"]):
                score += 500
            try:
                var = df[c].var()
                if pd.notna(var) and var > 0:
                    score += min(100, float(np.log1p(var)))
            except Exception:
                pass
            return score

        metric_candidates.sort(key=metric_score, reverse=True)
        primary_metric = metric_candidates[0]
    else:
        primary_metric = "_row_count"

    # Rank Category columns
    primary_category = None
    secondary_category = None
    if category_candidates:
        def category_score(c):
            score = 0.0
            cl = str(c).lower()
            n = df[c].nunique()
            if 4 <= n <= 300:
                score += 50
            elif 2 <= n < 4:
                score += 20
            else:
                score += 15

            if any(k in cl for k in ["country", "state", "region", "city", "market"]):
                score += 100
            if any(k in cl for k in ["category", "segment", "type", "class", "sector", "commodity", "product", "dept", "department"]):
                score += 80
            return score

        category_candidates.sort(key=category_score, reverse=True)
        primary_category = category_candidates[0]
        if len(category_candidates) > 1:
            secondary_category = category_candidates[1]
        else:
            secondary_category = primary_category

    # Determine Range Filter column and min/max
    detected_range = {}
    if time_col is not None:
        s = df[time_col].dropna()
        if pd.api.types.is_numeric_dtype(s):
            detected_range = {
                "col_name": time_col,
                "type": "time_numeric",
                "min": int(s.min()),
                "max": int(s.max()),
                "step": 1,
            }
        else:
            detected_range = {
                "col_name": time_col,
                "type": "time_string",
                "min": str(s.min()),
                "max": str(s.max()),
                "step": 1,
            }
    elif primary_metric and primary_metric != "_row_count":
        s = df[primary_metric].dropna()
        p_min = float(s.min()) if len(s) else 0.0
        p_max = float(s.max()) if len(s) else 100.0
        detected_range = {
            "col_name": primary_metric,
            "type": "numeric",
            "min": round(p_min, 2),
            "max": round(p_max, 2),
            "step": round(max(0.1, (p_max - p_min) / 100.0), 2),
        }
    else:
        detected_range = {
            "col_name": "Row Index",
            "type": "index",
            "min": 1,
            "max": max(1, total_rows),
            "step": 1,
        }

    # Available modules list
    available_modules = ["kpis", "insights", "stats_summary", "trend", "distribution", "data_quality"]
    if primary_category is not None:
        available_modules.append("top_categories")
        available_modules.append("composition")
    if len(metric_candidates) >= 2:
        available_modules.append("correlation")

    return {
        "time_col": time_col,
        "id_cols": id_cols,
        "metric_cols": metric_candidates,
        "category_cols": category_candidates,
        "primary_metric": primary_metric,
        "primary_category": primary_category,
        "secondary_category": secondary_category,
        "detected_range": detected_range,
        "available_modules": available_modules,
    }


def compute_clean_dataframe(df: pd.DataFrame) -> (pd.DataFrame, Dict[str, Any]):
    """
    One-click automated data cleaning:
    - Drops exact duplicates
    - Imputes numeric columns with median (or 0)
    - Imputes categorical columns with 'Unknown'
    - Trims string whitespaces
    """
    initial_rows = len(df)
    initial_missing = int(df.isna().sum().sum())
    initial_duplicates = int(df.duplicated().sum())

    cleaned = df.copy()

    # 1. Drop duplicates
    cleaned = cleaned.drop_duplicates()
    dropped_duplicates = initial_rows - len(cleaned)

    imputed_numeric_count = 0
    imputed_category_count = 0

    # 2. Impute and trim columns
    for col in cleaned.columns:
        if pd.api.types.is_numeric_dtype(cleaned[col]):
            null_count = int(cleaned[col].isna().sum())
            if null_count > 0:
                med = cleaned[col].median()
                fill_val = 0 if pd.isna(med) else med
                cleaned[col] = cleaned[col].fillna(fill_val)
                imputed_numeric_count += null_count
        else:
            null_count = int(cleaned[col].isna().sum())
            if null_count > 0:
                cleaned[col] = cleaned[col].fillna("Unknown")
                imputed_category_count += null_count
            if cleaned[col].dtype == object or isinstance(cleaned[col].dtype, pd.StringDtype):
                cleaned[col] = cleaned[col].astype(str).str.strip()

    stats = {
        "before": {
            "row_count": initial_rows,
            "missing_count": initial_missing,
            "duplicate_count": initial_duplicates,
        },
        "after": {
            "row_count": len(cleaned),
            "missing_count": int(cleaned.isna().sum().sum()),
            "duplicate_count": int(cleaned.duplicated().sum()),
        },
        "dropped_duplicates": dropped_duplicates,
        "imputed_numeric_count": imputed_numeric_count,
        "imputed_category_count": imputed_category_count,
    }
    return cleaned, stats


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Accepts any uploaded CSV file, profiles its schema automatically,
    and returns dataset metadata with detected range and module availability.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except UnicodeDecodeError:
        df = pd.read_csv(io.BytesIO(content), encoding="latin1")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded CSV file is empty.")

    # Clean column headers
    df.columns = [str(c).strip() for c in df.columns]

    # Run profiling
    profile = profile_dataframe(df)
    cleaned_df, clean_stats = compute_clean_dataframe(df)

    # Save to state
    dataset_state.raw_df = df
    dataset_state.cleaned_df = cleaned_df
    dataset_state.filename = file.filename
    dataset_state.profile = profile
    dataset_state.clean_stats = clean_stats

    metadata = {
        "filename": file.filename,
        "row_count": len(df),
        "col_count": len(df.columns),
        "missing_count": int(df.isna().sum().sum()),
        "duplicate_count": int(df.duplicated().sum()),
        "detected_range": profile["detected_range"],
        "available_modules": profile["available_modules"],
        "profile": {
            "time_col": profile["time_col"],
            "id_cols": profile["id_cols"],
            "primary_metric": profile["primary_metric"],
            "primary_category": profile["primary_category"],
            "secondary_category": profile["secondary_category"],
            "all_metrics": profile["metric_cols"],
            "all_categories": profile["category_cols"],
        },
        "clean_stats": clean_stats,
    }
    dataset_state.metadata = metadata
    return sanitize(metadata)


@app.post("/api/load-sample")
def load_sample_dataset():
    """
    Instantly loads the bundled Cleaned_India_Export.csv for zero-effort demonstration.
    """
    if not SAMPLE_FILE.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found.")

    df = pd.read_csv(SAMPLE_FILE)
    df.columns = [str(c).strip() for c in df.columns]

    profile = profile_dataframe(df)
    cleaned_df, clean_stats = compute_clean_dataframe(df)

    dataset_state.raw_df = df
    dataset_state.cleaned_df = cleaned_df
    dataset_state.filename = "Cleaned_India_Export.csv"
    dataset_state.profile = profile
    dataset_state.clean_stats = clean_stats

    metadata = {
        "filename": "Cleaned_India_Export.csv",
        "row_count": len(df),
        "col_count": len(df.columns),
        "missing_count": int(df.isna().sum().sum()),
        "duplicate_count": int(df.duplicated().sum()),
        "detected_range": profile["detected_range"],
        "available_modules": profile["available_modules"],
        "profile": {
            "time_col": profile["time_col"],
            "id_cols": profile["id_cols"],
            "primary_metric": profile["primary_metric"],
            "primary_category": profile["primary_category"],
            "secondary_category": profile["secondary_category"],
            "all_metrics": profile["metric_cols"],
            "all_categories": profile["category_cols"],
        },
        "clean_stats": clean_stats,
    }
    dataset_state.metadata = metadata
    return sanitize(metadata)


@app.post("/api/clean")
def trigger_clean():
    """
    Returns before-vs-after cleaning statistics and confirms active cleaned mode.
    """
    if dataset_state.raw_df is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload a CSV first.")

    cleaned_df, clean_stats = compute_clean_dataframe(dataset_state.raw_df)
    dataset_state.cleaned_df = cleaned_df
    dataset_state.clean_stats = clean_stats
    return sanitize(clean_stats)


class GenerateRequest(BaseModel):
    modules: List[str] = [
        "kpis",
        "insights",
        "stats_summary",
        "trend",
        "top_categories",
        "composition",
        "distribution",
        "correlation",
        "data_quality",
    ]
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    use_cleaned: bool = False


@app.post("/api/generate")
def generate_visualizations(req: GenerateRequest):
    """
    Filters the DataFrame by the selected range and computes ready-to-render
    JSON data for only the requested visualization modules.
    """
    if dataset_state.raw_df is None:
        raise HTTPException(status_code=400, detail="No dataset loaded. Please upload a CSV first.")

    working_df = dataset_state.cleaned_df if req.use_cleaned else dataset_state.raw_df
    if working_df is None:
        working_df = dataset_state.raw_df

    profile = dataset_state.profile
    time_col = profile.get("time_col")
    primary_metric = profile.get("primary_metric")
    primary_category = profile.get("primary_category")
    secondary_category = profile.get("secondary_category")
    metric_cols = profile.get("metric_cols", [])

    df = working_df.copy()
    if primary_metric == "_row_count":
        df["_row_count"] = 1

    # Apply Range Filter
    range_col = profile.get("detected_range", {}).get("col_name")
    if range_col and range_col in df.columns:
        if req.range_min is not None and req.range_max is not None:
            if pd.api.types.is_numeric_dtype(df[range_col]):
                df = df[(df[range_col] >= req.range_min) & (df[range_col] <= req.range_max)]
            else:
                df = df[(df[range_col].astype(str) >= str(req.range_min)) & (df[range_col].astype(str) <= str(req.range_max))]

    results: Dict[str, Any] = {}

    # 1. KPIs Module
    if "kpis" in req.modules:
        total_rows = len(df)
        total_cells = df.shape[0] * df.shape[1]
        missing_cells = int(df.isna().sum().sum())
        completeness = round((1.0 - (missing_cells / total_cells)) * 100.0, 2) if total_cells > 0 else 100.0
        dup_count = int(df.duplicated().sum())

        metric_sum = float(df[primary_metric].sum()) if primary_metric in df.columns else 0.0
        metric_mean = float(df[primary_metric].mean()) if primary_metric in df.columns else 0.0
        top_cat_unique = int(df[primary_category].nunique()) if primary_category and primary_category in df.columns else 0

        results["kpis"] = {
            "total_rows": total_rows,
            "metric_sum": metric_sum,
            "metric_mean": metric_mean,
            "metric_name": primary_metric if primary_metric != "_row_count" else "Records",
            "top_category_unique": top_cat_unique,
            "category_name": primary_category or "Categories",
            "completeness_pct": completeness,
            "duplicate_count": dup_count,
            "auto_reason": f"Primary metric '{primary_metric}' paired with '{primary_category or 'rows'}'",
        }

    # 2. Executive Insights Module (4 crisp human-readable analytical points)
    if "insights" in req.modules:
        insights_items = []

        # (a) Trend Insight
        if time_col and time_col in df.columns:
            grouped = df.groupby(time_col)[primary_metric].sum().sort_index()
            if len(grouped) > 0:
                peak_period = str(grouped.idxmax())
                peak_val = float(grouped.max())
                low_period = str(grouped.idxmin())
                low_val = float(grouped.min())
                start_val = float(grouped.iloc[0])
                start_period = str(grouped.index[0])
                end_val = float(grouped.iloc[-1])
                end_period = str(grouped.index[-1])
                growth_pct = ((end_val - start_val) / abs(start_val) * 100.0) if start_val != 0 else 0.0
                growth_dir = "growth" if growth_pct >= 0 else "decline"

                trend_text = (
                    f"Volume peaked in {peak_period} ({peak_val:,.2f}) and hit its lowest level in {low_period} "
                    f"({low_val:,.2f}). Across the range ({start_period} to {end_period}), aggregate {primary_metric} "
                    f"registered an overall {abs(growth_pct):.1f}% {growth_dir}."
                )
            else:
                trend_text = "Insufficient temporal observations in the selected range."
        else:
            seq_sum = float(df[primary_metric].sum()) if primary_metric in df.columns else 0.0
            seq_min = float(df[primary_metric].min()) if primary_metric in df.columns else 0.0
            seq_max = float(df[primary_metric].max()) if primary_metric in df.columns else 0.0
            trend_text = (
                f"Across {len(df):,} sequential records, {primary_metric} accumulates to {seq_sum:,.2f}, "
                f"with record-level values spanning from {seq_min:,.2f} to {seq_max:,.2f}."
            )

        insights_items.append({
            "title": "Trend & Trajectory",
            "text": trend_text,
            "category": "trend",
        })

        # (b) Dominance / Pareto Insight
        top2_share = 0.0
        if primary_category and primary_category in df.columns and primary_metric in df.columns:
            cat_sum = df.groupby(primary_category)[primary_metric].sum().sort_values(ascending=False)
            total_val = float(cat_sum.sum())
            if total_val > 0 and len(cat_sum) >= 1:
                top1_name = str(cat_sum.index[0])
                top1_val = float(cat_sum.iloc[0])
                top1_share = (top1_val / total_val) * 100.0

                if len(cat_sum) >= 2:
                    top2_name = str(cat_sum.index[1])
                    top2_val = float(cat_sum.iloc[1])
                    top2_share = ((top1_val + top2_val) / total_val) * 100.0
                    pareto_text = (
                        f"The leading group '{top1_name}' holds {top1_share:.1f}% of total {primary_metric}. "
                        f"Together with '{top2_name}', the top 2 groups capture {top2_share:.1f}% of aggregate volume "
                        f"across all {len(cat_sum):,} active categories."
                    )
                else:
                    top2_share = top1_share
                    pareto_text = f"The single group '{top1_name}' represents 100.0% of total {primary_metric}."
            else:
                pareto_text = "Category aggregates are zero across the active range."
        else:
            pareto_text = "Single-dimension dataset without category grouping."

        insights_items.append({
            "title": "Dominance & Pareto Share",
            "text": pareto_text,
            "category": "pareto",
        })

        # (c) Distribution & Outlier Insight
        if primary_metric in df.columns and len(df[primary_metric].dropna()) > 0:
            s_metric = df[primary_metric].dropna()
            m_mean = float(s_metric.mean())
            m_med = float(s_metric.median())
            m_skew = float(s_metric.skew()) if len(s_metric) > 2 else 0.0

            if m_med != 0:
                gap_mult = m_mean / m_med
            else:
                gap_mult = 1.0

            if m_skew > 1.0:
                dist_text = (
                    f"The mean ({m_mean:,.2f}) significantly exceeds the median ({m_med:,.2f}) by {gap_mult:.1f}x "
                    f"with a strong positive skew of +{m_skew:.2f}. Extreme high-value outliers are pulling the "
                    f"arithmetic average well above typical baseline records."
                )
            elif m_skew < -1.0:
                dist_text = (
                    f"The mean ({m_mean:,.2f}) sits below the median ({m_med:,.2f}) with a negative skew of "
                    f"{m_skew:.2f}. Lower-bound observations are exerting downward pull on aggregate averages."
                )
            else:
                dist_text = (
                    f"The mean ({m_mean:,.2f}) closely tracks the median ({m_med:,.2f}) with a balanced skew of "
                    f"{m_skew:.2f}, indicating a symmetric distribution free of disruptive outlier leverage."
                )
        else:
            dist_text = "No numeric metric distribution available to assess."

        insights_items.append({
            "title": "Distribution & Outlier Leverage",
            "text": dist_text,
            "category": "distribution",
        })

        # (d) Data Quality & Bias Insight
        missing_count = int(df.isna().sum().sum())
        total_cells = df.shape[0] * df.shape[1]
        missing_pct = (missing_count / total_cells * 100.0) if total_cells > 0 else 0.0
        dup_count = int(df.duplicated().sum())

        concentration_flag = ""
        if primary_category and primary_category in df.columns and primary_metric in df.columns:
            if top2_share > 25.0:
                concentration_flag = f"Concentration bias detected: top 2 categories control {top2_share:.1f}% of total volume (exceeds 25.0% threshold)."
            else:
                concentration_flag = f"Category volume is diversified: top 2 categories capture {top2_share:.1f}% (below 25.0% threshold)."

        bias_text = (
            f"Data integrity audit reports {missing_count:,} missing values ({missing_pct:.2f}% of total cells) "
            f"and {dup_count:,} exact duplicate rows. {concentration_flag}".strip()
        )

        insights_items.append({
            "title": "Data Quality & Bias",
            "text": bias_text,
            "category": "quality",
        })

        results["insights"] = {
            "items": insights_items,
            "auto_reason": "Programmatically synthesized macro findings",
        }

    # 3. Statistical Summary Module (df.describe() across all numeric columns)
    if "stats_summary" in req.modules:
        stat_rows = []
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != "_row_count"]
        total_df_rows = len(df)

        for col in num_cols:
            s = df[col].dropna()
            c_count = int(len(s))
            c_missing = int(df[col].isna().sum())
            c_missing_pct = round((c_missing / total_df_rows) * 100.0, 2) if total_df_rows > 0 else 0.0

            c_mean = round(float(s.mean()), 2) if c_count > 0 else 0.0
            c_std = round(float(s.std()), 2) if c_count > 1 else 0.0
            c_min = round(float(s.min()), 2) if c_count > 0 else 0.0
            c_median = round(float(s.median()), 2) if c_count > 0 else 0.0
            c_max = round(float(s.max()), 2) if c_count > 0 else 0.0
            c_skew = round(float(s.skew()), 2) if c_count > 2 else 0.0

            stat_rows.append({
                "column": col,
                "count": c_count,
                "mean": c_mean,
                "std": c_std,
                "min": c_min,
                "median": c_median,
                "max": c_max,
                "skewness": c_skew,
                "missing_pct": c_missing_pct,
            })

        results["stats_summary"] = {
            "rows": stat_rows,
            "auto_reason": f"Descriptive statistical summary across {len(num_cols)} numeric dimensions",
        }

    # 4. Trend Module
    if "trend" in req.modules:
        if time_col and time_col in df.columns:
            grouped = df.groupby(time_col)[primary_metric].sum().sort_index()
            results["trend"] = {
                "x": grouped.index.astype(str).tolist(),
                "y": grouped.values.round(2).tolist(),
                "x_label": time_col,
                "y_label": f"Sum of {primary_metric}",
                "auto_reason": f"Auto-selected '{primary_metric}' aggregated over time column '{time_col}'",
            }
        else:
            rolling_window = max(5, min(100, len(df) // 30))
            rolling_series = df[primary_metric].rolling(window=rolling_window, min_periods=1).mean()
            step = max(1, len(df) // 100)
            sampled_indices = list(range(0, len(df), step))
            results["trend"] = {
                "x": sampled_indices,
                "y": rolling_series.iloc[sampled_indices].round(2).tolist(),
                "x_label": "Row Index (Sequence)",
                "y_label": f"Rolling Mean ({primary_metric})",
                "auto_reason": f"No time column detected; calculated rolling index sequence for '{primary_metric}'",
            }

    # 5. Top Categories Module (Truncate to 28 chars with ... on y-axis, retain full in hover)
    if "top_categories" in req.modules:
        if primary_category and primary_category in df.columns:
            top_series = df.groupby(primary_category)[primary_metric].sum().nlargest(10)
            top_series_rev = top_series.iloc[::-1]
            full_names = top_series_rev.index.astype(str).tolist()
            truncated_names = [(c[:25] + "..." if len(c) > 28 else c) for c in full_names]

            results["top_categories"] = {
                "categories": truncated_names,
                "full_categories": full_names,
                "values": top_series_rev.values.round(2).tolist(),
                "category_col": primary_category,
                "metric_col": primary_metric,
                "auto_reason": f"Top 10 '{primary_category}' ranked by aggregate '{primary_metric}'",
            }
        else:
            results["top_categories"] = {
                "categories": [],
                "full_categories": [],
                "values": [],
                "category_col": "None",
                "metric_col": primary_metric,
                "auto_reason": "No categorical column with valid cardinality found",
            }

    # 6. Composition Module
    if "composition" in req.modules:
        cat_to_use = secondary_category if (secondary_category and secondary_category in df.columns) else primary_category
        if cat_to_use and cat_to_use in df.columns:
            comp_series = df.groupby(cat_to_use)[primary_metric].sum().sort_values(ascending=False)
            top5 = comp_series.head(5)
            labels = top5.index.astype(str).tolist()
            values = top5.values.round(2).tolist()

            if len(comp_series) > 5:
                other_sum = float(comp_series.iloc[5:].sum())
                if other_sum > 0:
                    labels.append("Other")
                    values.append(round(other_sum, 2))

            cleaned_labels = [l[:28] + "..." if len(l) > 28 else l for l in labels]

            results["composition"] = {
                "labels": cleaned_labels,
                "full_labels": labels,
                "values": values,
                "category_col": cat_to_use,
                "metric_col": primary_metric,
                "auto_reason": f"Top 5 '{cat_to_use}' distribution by '{primary_metric}' with 'Other' group",
            }
        else:
            results["composition"] = {
                "labels": [],
                "full_labels": [],
                "values": [],
                "category_col": "None",
                "metric_col": primary_metric,
                "auto_reason": "No suitable categorical grouping column found",
            }

    # 7. Distribution Module
    if "distribution" in req.modules:
        metric_series = df[primary_metric].dropna() if primary_metric in df.columns else pd.Series(dtype=float)
        if len(metric_series) > 0:
            num_bins = min(30, max(8, int(len(metric_series) ** 0.4)))
            counts, bin_edges = np.histogram(metric_series, bins=num_bins)
            bin_mids = [round(float((bin_edges[i] + bin_edges[i+1]) / 2), 2) for i in range(len(counts))]

            q1 = float(np.percentile(metric_series, 25))
            median = float(np.percentile(metric_series, 50))
            q3 = float(np.percentile(metric_series, 75))

            skew = float(metric_series.skew()) if len(metric_series) > 2 else 0.0
            if skew > 1.0:
                skew_desc = f"Right-skewed (skew: +{skew:.2f}) — long tail with high-value outliers."
            elif skew < -1.0:
                skew_desc = f"Left-skewed (skew: {skew:.2f}) — concentrated toward higher values."
            else:
                skew_desc = f"Approximately symmetric (skew: {skew:.2f})."

            sample_pts = metric_series.sample(min(500, len(metric_series)), random_state=42).tolist()

            results["distribution"] = {
                "hist_x": bin_mids,
                "hist_y": counts.tolist(),
                "sample_points": sample_pts,
                "stats": {
                    "mean": round(float(metric_series.mean()), 2),
                    "median": round(median, 2),
                    "std": round(float(metric_series.std()), 2) if len(metric_series) > 1 else 0.0,
                    "min": round(float(metric_series.min()), 2),
                    "max": round(float(metric_series.max()), 2),
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "skew": round(skew, 2),
                    "skew_interpretation": skew_desc,
                },
                "auto_reason": f"Distribution & outlier spread for '{primary_metric}'",
            }
        else:
            results["distribution"] = {
                "hist_x": [],
                "hist_y": [],
                "stats": {},
                "auto_reason": "No metric data available for distribution",
            }

    # 8. Correlation Module (Only if >= 2 numeric columns)
    if "correlation" in req.modules:
        valid_numeric_cols = [c for c in metric_cols if c in df.columns]
        if len(valid_numeric_cols) >= 2:
            subset_cols = valid_numeric_cols[:8]
            corr_matrix = df[subset_cols].corr().round(2)
            results["correlation"] = {
                "available": True,
                "columns": subset_cols,
                "z": corr_matrix.values.tolist(),
                "auto_reason": f"Pearson pairwise correlation across {len(subset_cols)} numeric metrics",
            }
        else:
            results["correlation"] = {
                "available": False,
                "columns": [],
                "z": [],
                "auto_reason": "Requires at least 2 numeric metric columns",
            }

    # 9. Data Quality & Bias Module (No emojis or sirens)
    if "data_quality" in req.modules:
        missing_pcts = ((df.isna().sum() / max(1, len(df))) * 100.0).round(2).to_dict()
        columns = list(missing_pcts.keys())
        missing_vals = list(missing_pcts.values())

        bias_warnings = []

        if primary_category and primary_category in df.columns and primary_metric in df.columns:
            cat_sum = df.groupby(primary_category)[primary_metric].sum().sort_values(ascending=False)
            total_sum = cat_sum.sum()
            if total_sum > 0 and len(cat_sum) >= 2:
                top2_share = (cat_sum.iloc[:2].sum() / total_sum) * 100.0
                if top2_share >= 50.0:
                    bias_warnings.append(
                        f"Pareto Asymmetry Alert: Top 2 '{primary_category}' ({cat_sum.index[0]}, {cat_sum.index[1]}) absorb {top2_share:.1f}% of total {primary_metric}."
                    )
                elif top2_share >= 25.0:
                    bias_warnings.append(
                        f"High Concentration: Top 2 '{primary_category}' ({cat_sum.index[0]}, {cat_sum.index[1]}) command {top2_share:.1f}% of {primary_metric}."
                    )

                if len(cat_sum) >= 5:
                    top5_share = (cat_sum.iloc[:5].sum() / total_sum) * 100.0
                    if top5_share >= 70.0:
                        bias_warnings.append(
                            f"Corridor Dependency: Top 5 '{primary_category}' capture {top5_share:.1f}% of all transactions."
                        )

        for c, pct in missing_pcts.items():
            if pct >= 20.0:
                bias_warnings.append(f"High Incompleteness: Column '{c}' is {pct:.1f}% missing.")

        for c in df.columns:
            if df[c].nunique(dropna=True) <= 1:
                bias_warnings.append(f"Invariant Dimension: Column '{c}' has only 1 distinct value.")

        if not bias_warnings:
            bias_warnings.append("Clean Distribution: No severe Pareto concentration or missingness anomalies detected.")

        results["data_quality"] = {
            "columns": columns,
            "missing_pcts": missing_vals,
            "bias_warnings": bias_warnings,
            "auto_reason": "Missing value completeness audit and Pareto concentration heuristics",
        }

    return sanitize(results)


@app.get("/api/status")
def get_status():
    """
    Returns current dataset status.
    """
    if dataset_state.raw_df is None:
        return {"loaded": False}
    return {
        "loaded": True,
        "filename": dataset_state.filename,
        "row_count": len(dataset_state.raw_df),
        "clean_stats": dataset_state.clean_stats,
    }


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
