"""
India Exports EDA - FastAPI backend.
Run:  uvicorn main:app --reload
"""

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "Cleaned_India_Export.csv"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="India Exports EDA API")


def load_data() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"{DATA_FILE.name} not found next to main.py")
    df = pd.read_csv(DATA_FILE)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["year", "value", "country", "Commodity"])
    df["year"] = df["year"].astype(int)
    return df


# Loaded once at startup; restart the server if the CSV changes.
df = load_data()


def filter_year(year: Optional[int]) -> pd.DataFrame:
    if year is None:
        return df
    sub = df[df["year"] == year]
    if sub.empty:
        raise HTTPException(status_code=404, detail=f"No data for year {year}")
    return sub


@app.get("/api/years")
def years():
    return {"years": sorted(df["year"].unique().tolist())}


@app.get("/api/summary")
def summary(year: Optional[int] = Query(None)):
    sub = filter_year(year)
    return {
        "total_value": float(sub["value"].sum()),
        "countries": int(sub["country"].nunique()),
        "commodities": int(sub["Commodity"].nunique()),
    }


@app.get("/api/trend")
def trend():
    """Total export value per year (always all years)."""
    t = df.groupby("year")["value"].sum().sort_index()
    return {"labels": t.index.tolist(), "values": t.round(2).tolist()}


@app.get("/api/top-countries")
def top_countries(year: Optional[int] = Query(None)):
    sub = filter_year(year)
    t = sub.groupby("country")["value"].sum().nlargest(10)
    return {"labels": t.index.tolist(), "values": t.round(2).tolist()}


@app.get("/api/top-commodities")
def top_commodities(year: Optional[int] = Query(None)):
    sub = filter_year(year)
    t = sub.groupby("Commodity")["value"].sum().nlargest(5)
    return {"labels": t.index.tolist(), "values": t.round(2).tolist()}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
