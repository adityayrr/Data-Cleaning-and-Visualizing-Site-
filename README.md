# India Exports Explorer

A lightweight full-stack dashboard for exploratory data analysis (EDA) of India's export data. A **FastAPI** backend aggregates the data with **Pandas**, and a **vanilla HTML/CSS/JS** frontend renders interactive **Chart.js** charts in a dark, minimalist theme (AMOLED black, Spotify green, warm white) using the Agrave Pro typeface.

## Features

- **Total export value trend** across all years (line chart)
- **Top 10 countries** by total value (horizontal bar chart)
- **Top 5 commodities** by total value (doughnut chart)
- **Year filter** that updates the summary cards, bar chart and doughnut chart; the line chart always shows every year, with the selected year highlighted
- **Summary cards** for total value, number of countries and number of commodities
- No build step: plain static files served directly by FastAPI

## Tech Stack

| Layer    | Tools                                  |
|----------|----------------------------------------|
| Backend  | Python, FastAPI, Uvicorn, Pandas       |
| Frontend | HTML, CSS, JavaScript, Chart.js (CDN)  |

## Project Structure

```
dashboard/
├── main.py                       # FastAPI app and API endpoints
├── requirements.txt              # Python dependencies
├── Cleaned_India_Export.csv      # Your dataset (add this yourself)
└── static/
    ├── index.html
    ├── style.css
    ├── script.js
    └── fonts/
        ├── AgravePro-VariableFont_wght.ttf
        └── AgravePro-Regular.ttf
```

## Dataset

Place a file named `Cleaned_India_Export.csv` in the project root (next to `main.py`) with these columns:

| Column      | Description                                      |
|-------------|--------------------------------------------------|
| `year`      | Year of the record (e.g. `2020` or `2018-19`)    |
| `value`     | Export value (numeric; commas are tolerated)     |
| `country`   | Destination country                              |
| `Commodity` | Exported commodity                               |

Rows with missing values in any of these columns are dropped. Nothing is generated or estimated.

## Getting Started

### Prerequisites

- Python 3.9 or newer

### Installation and run

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

> Open the dashboard through the FastAPI server. Opening `index.html` directly or through another static server (such as VS Code Live Server) will not work, because the page calls the `/api/...` endpoints on the same origin.

Interactive API documentation is available at **http://127.0.0.1:8000/docs**.

## API Endpoints

| Method | Endpoint                          | Description                                     |
|--------|-----------------------------------|-------------------------------------------------|
| GET    | `/api/years`                      | List of available years                         |
| GET    | `/api/summary?year=`              | Total value, country count, commodity count     |
| GET    | `/api/trend`                      | Total value per year                            |
| GET    | `/api/top-countries?year=`        | Top 10 countries by total value                 |
| GET    | `/api/top-commodities?year=`      | Top 5 commodities by total value                |

The `year` parameter is optional on every endpoint that accepts it; omitting it aggregates across all years.

Example response:

```json
{
  "labels": ["Country A", "Country B"],
  "values": [1234.56, 987.65]
}
```

## Customization

- **Colors:** edit the CSS variables at the top of `static/style.css` and the `C` object at the top of `static/script.js`.
- **Fonts:** swap the files in `static/fonts/` and update the `@font-face` rule in `style.css` and the font family in `script.js`.
- **Top-N limits:** change `nlargest(10)` and `nlargest(5)` in `main.py`.

## Troubleshooting

- **"Could not load data" or empty charts:** check the terminal for the `[startup]` lines showing how many rows loaded. If "usable rows" is 0 or far lower than "Loaded", check the `year` and `value` columns in your CSV.
- **Verify the API directly:** open http://127.0.0.1:8000/api/years. You should see a JSON list of years.
- **Data changes not showing:** the CSV is read once at startup. Restart the server after editing it.
- **Font not applied:** confirm `static/fonts/AgravePro-VariableFont_wght.ttf` exists and loads (no 404) in your browser's Network tab.

## Notes

- The units of `value` depend on your dataset, so the charts do not label units.
- Agrave Pro is a third-party typeface. Check its license before redistributing the font files in a public repository.
