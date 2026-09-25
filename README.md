# Vayu Health

Live coverage now includes **42 Indian cities**, independent pollutant forecasting,
and explicitly labelled CAMS regional estimates when station coverage is missing.
See [the forecasting and response design](docs/RESILIENT_FORECASTING.md) for what
is implemented, evaluation methods, and the field validation still required.

**New here? Read [RUN_GUIDE.md](RUN_GUIDE.md)** for installation, live editing, local execution, testing, and OpenAQ timeout troubleshooting. Run `./diagnose.ps1` for a safe provider connectivity report.

Air-quality intelligence for earlier action. Implements the core dashboard described in **VAYU.pdf / PS-1A**: PM2.5 and PM10 forecasts, public-health outlooks, station mapping, explainability, and human-reviewed industrial recommendations.

## Run locally (Windows)

Requires Python 3.11 and Node.js 20.19+ or 22+. From this project directory:

```powershell
./start.ps1 -Setup
```

The script installs dependencies, builds the website, and serves the complete application at **http://localhost:8000**. Subsequent launches use `./start.ps1`. Use `-Port 8001` if necessary. Stop with Ctrl+C. API documentation is at `/docs`. The script preserves your existing `.env`.

For live observations, set `OPENAQ_API_KEY` in `.env` and restart the API. Obtain a key from [OpenAQ Explorer](https://explore.openaq.org/account). The key is server-only; never use a `VITE_` variable for credentials. Open-Meteo weather needs no key for its public non-commercial endpoint. `AIRNOW_API_KEY` is reserved and currently **not used**. There is no need to wait for AirNow.

The website opens in **Live data** mode. If credentials, upstream availability, or recent paired measurements are missing, it shows an actionable error. **Demo** is a deliberate user selection and is prominently labeled as synthetic throughout. It is never a silent live fallback.

### Development

```powershell
# Terminal 1, project root
./.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
# Terminal 2, project root
npm.cmd --prefix frontend run dev
```

Vite serves http://localhost:5173 and proxies API requests to port 8000. The production build is served by FastAPI on port 8000. An optional `VITE_API_URL` can point a separately hosted frontend to the backend; configure `CORS_ORIGINS` accordingly.

## Website

| View             | Features                                                                                                                           |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Overview         | Current complete-hour PM, clearly labeled hourly risk index, forecast peak, weather, health outlook, monitoring map, model drivers |
| Forecasts        | PM2.5/PM10 switch, 24-hour forecast or 72-hour history, calibration bands, hourly table, CSV download with source/mode             |
| Station explorer | OpenStreetMap map, clickable real station markers, provider attribution, station search, pollutant values and observation age      |
| Health alerts    | Forecast warnings, affected groups, validity window, risk categories and standards explanation                                     |
| Action planner   | Suggested industrial checks, session-only review ticks, explicitly hypothetical concentration-reduction slider                     |
| Model & data     | Provenance, coverage, chronological validation, persistence comparison, MAE/RMSE/R², alert precision/recall/F1, limitations        |

Available cities: Delhi, Mumbai, Los Angeles, London, Beijing. Live coverage depends on OpenAQ stations; inclusion in this list does not guarantee current paired PM coverage. The map shows actual station coordinates in live mode; demo mode shows only the city centre. OpenStreetMap tiles and Google Fonts need network access; core dashboard text uses local font fallbacks.

## Data pipeline

1. Discover stations within **125 km** using OpenAQ's bounding-box query followed by a circular distance filter (the API's direct radius parameter is capped at 25 km).
2. Resolve each latest reading's `sensorsId` through station sensor metadata. Accept PM2.5/PM10 concentration units only, reject negative/non-finite values, preserve timestamps, and exclude readings older than 24 hours.
3. Select one station with both pollutants, then paginate up to 45 days of `/sensors/{id}/hours`. Require at least 75% coverage for an hourly aggregate when coverage metadata exists. Duplicate hourly timestamps are averaged.
4. Join to hourly Open-Meteo weather in UTC. Older weather is reanalysis; recent weather comes from the forecast API's past window. The OpenAQ key is **never** sent to the weather provider.
5. Reindex hourly so missing hours cannot masquerade as adjacent observations. Missing values are not filled with synthetic observations. Supervised samples spanning gaps are excluded.
6. Cache successful collection for 10 minutes; save real aligned history under `data/processed/`. Model artifacts include a data fingerprint and mode to keep real and synthetic models separate.

Live current values use the latest complete **hourly** record. The station table uses the provider's latest individual readings, which can differ in timestamp. Forecasts originate at the complete hour, not the request time. A station is not a city-wide average and relative station pollution does not establish emission sources.

## Forecasting and honest evaluation

- Extra Trees produces both pollutants for 24 horizons directly, using current values, lags, rolling means, time and weather features.
- Earlier 65% training / 17% calibration / 18% test, with **24 sample-origin gaps** between splits. Because the grid is hourly before filtering, those gaps are at least 24 hours and prevent overlapping target leakage.
- Compare model MAE, RMSE and R² against persistence on exactly the same held-out samples. Alert precision, recall and F1 use hourly risk index 151 thresholds. Overlapping horizons are not independent events; no seasonal generalization is claimed.
- Bands use the 90th percentile of absolute calibration errors per horizon. They are indicative error ranges, not guaranteed confidence intervals.
- Global tree feature importance is shown. The Forecasts view also explains the current prediction using grouped sensitivity: replace one feature group with its training median and measure the change in mean 24-hour predicted concentration. These effects are not additive, are not SHAP values, and are not causal evidence.
- With insufficient usable history (400 supervised origins), recent missing hours, or insufficient split sizes, use an explicitly labeled **persistence baseline** without invented evaluation scores or intervals.

```powershell
$env:PYTHONPATH='backend'
./.venv/Scripts/python.exe -m app.ml.train --city delhi --mode live
# Explicit offline demonstration:
./.venv/Scripts/python.exe -m app.ml.train --city delhi --mode demo
```

## Risk standards and operational scope

Uses the [US EPA 2024 particulate breakpoints](https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-final-frn-pre-publication_0.pdf), with PM2.5 truncated to 0.1 µg/m³ and PM10 to whole µg/m³. Applying these to hourly concentrations yields a **screening risk index**, not an official daily AQI, a calculated NowCast, or India's CPCB AQI. [EPA AQI guidance](https://www.airnow.gov/aqi/aqi-basics/) provides category context.

Recommendations are rule-based decision support for operator validation, not autonomous equipment control or claimed optimized reductions. Industrial areas are catalog entries, not geolocated sources. No measured compliance, protected population, or intervention effect is claimed. The what-if tool only scales forecast concentrations mathematically. Alerts appear in-app; external delivery, accounts and persistent operator workflows are not implemented.

## API

| Method | Endpoint                                    | Behavior                                                                           |
| ------ | ------------------------------------------- | ---------------------------------------------------------------------------------- |
| GET    | `/health`                                   | Process liveness; does not imply provider availability                             |
| GET    | `/api/v1/status`                            | Non-sensitive configuration status                                                 |
| GET    | `/api/v1/locations`                         | Supported cities and industrial-area catalog                                       |
| GET    | `/api/v1/forecast/{city}?mode=live`         | Full snapshot, 24-hour forecast, stations, history, evaluation and recommendations |
| GET    | `/api/v1/history/{city}?hours=72&mode=live` | Up to 720 hourly rows, with nulls for missing values                               |

`mode=demo` explicitly selects synthetic data. Invalid cities return 404, invalid parameters 422, and known data-provider failures 503. API secrets are never returned. Public production hosting would additionally need authentication, abuse controls, and a durable shared ingestion scheduler; this setup is designed for a local hackathon deployment.

## Verification

```powershell
$env:PYTHONPATH='backend'
./.venv/Scripts/python.exe -m pytest backend/tests -q
npm.cmd --prefix frontend run build
```

Tests cover revised risk breakpoints, sensor/units mapping, invalid readings, pagination, explicit rate-limit errors, missing-hour handling, API validation and a full demo forecast. Live provider tests require credentials and network access and are separate from deterministic unit tests.

## Docker

```powershell
docker compose up --build
```

The multi-stage image builds the website and serves both UI and API at http://localhost:8000. `.env` is excluded from the image and supplied at runtime. Generated data and models use the compose volumes. Docker execution requires Docker Desktop.

## Project layout

```text
backend/app/data/openaq.py  Live collection, validation, weather and caching
backend/app/data/synthetic.py  Explicit offline demonstration
backend/app/ml/            Features, training, evaluation and forecasting
backend/app/services.py    Dashboard snapshot and decision-support assembly
backend/app/alerts.py      In-app public-health outlooks
backend/tests/             Deterministic integration and unit tests
frontend/src/              React/TypeScript UI and station map
data/processed/            Generated live hourly data (gitignored)
start.ps1                 Local setup, build and run
```

Sources: [OpenAQ v3 API](https://docs.openaq.org/api), [OpenAQ latest semantics](https://docs.openaq.org/resources/latest), [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api), [Open-Meteo forecast weather](https://open-meteo.com/en/docs).
