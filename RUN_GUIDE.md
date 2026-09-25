# Vayu Health: run, edit, verify

This guide is for Windows PowerShell. Run commands from the project root (the folder containing `frontend`, `backend`, and `start.ps1`). Keep each development terminal open while using the app.

## 1. First setup on your computer

Install **Python 3.11** and **Node.js 22 LTS**, then open a new PowerShell terminal. Do not copy another computer's `.venv` or `node_modules`; install these locally.

```powershell
Set-Location 'C:\Users\nikin\OneDrive\Documents\Hackathon\Vayu\Vayu-Health'
python --version
node --version
npm.cmd --version
```

Change the folder path if your copy is somewhere else. If `python --version` is not 3.11 and you have the Python launcher, use `py -3.11` instead of `python` in the next command.

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
```

Open `.env` in your editor and set `OPENAQ_API_KEY`. Do not put it into a React file or any `VITE_` variable. Leave `AIRNOW_API_KEY` blank: AirNow is not currently used. Open-Meteo supplies weather without an API key for its public non-commercial service.

## 2. Development mode: see your edits automatically

Use this mode when changing the code. The examples use **API port 8002** to avoid the existing demo on 8001 and any service on 8000.

**Terminal A — backend**

```powershell
Set-Location 'C:\Users\nikin\OneDrive\Documents\Hackathon\Vayu\Vayu-Health'
./.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --host 127.0.0.1 --port 8002
```

**Terminal B — website**

```powershell
Set-Location 'C:\Users\nikin\OneDrive\Documents\Hackathon\Vayu\Vayu-Health'
$env:VAYU_API_TARGET = 'http://127.0.0.1:8002'
npm.cmd --prefix frontend run dev
```

Open **http://localhost:5173**. The browser talks to Vite on 5173, and Vite forwards `/api` requests to your backend on 8002. API docs: **http://127.0.0.1:8002/docs**. Health check: **http://127.0.0.1:8002/health**.

If the app shows a provider error, choose **Demo** to work on the interface while investigating live connectivity. Demo data is synthetic.

### What happens after a file is saved?

| Your change | What you do |
| --- | --- |
| React, CSS, or frontend types | Save; Vite usually updates the page immediately. Refresh if necessary. |
| Python API/model code | Save; Uvicorn `--reload` restarts the backend. Wait for “Application startup complete,” then click Refresh in the app. |
| `.env`, API key, timeout settings | Stop Terminal A with Ctrl+C and rerun its command. Settings are cached; `.env` is not guaranteed to trigger automatic reload. |
| Vite config, proxy target, frontend environment | Stop and restart Terminal B. Set `VAYU_API_TARGET` again in a new terminal. |
| `frontend/package.json` dependencies | Run `npm.cmd --prefix frontend install`, then restart Vite. Commit the updated lockfile alongside the manifest. |
| `backend/requirements.txt` | Run `./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`, then restart the API. |

**Do not edit `frontend/dist`.** It is generated output and will be overwritten by the next build.

### Where to edit

| File | Purpose |
| --- | --- |
| `frontend/src/theme.css` | The earthy brutalist theme: palette tokens, borders, shadows, typography, card appearances |
| `frontend/src/styles.css` | Base layout, grid, spacing, responsive structure |
| `frontend/src/App.tsx` | Dashboard views, controls, charts, scenario logic and CSV export |
| `frontend/src/StationMap.tsx` | Station map, marker appearance and popups |
| `frontend/src/api.ts` | Frontend API requests |
| `backend/app/data/openaq.py` | Collection, weather alignment, quality checks, provider failures and retries |
| `backend/app/ml/model.py` | Forecasting, evaluation, calibration and explanation |
| `backend/app/alerts.py` | Health-outlook messages |
| `backend/app/catalog.py` | City and industrial-area catalog |
| `.env` | Your private runtime settings; never commit this file |

Theme colors: olive `#546B41`, sage `#99AD7A`, sand `#DCCCAC`, cream `#FFF8EC`, ink `#191B17`, and white `#FFFFFF`. Charts and markers also use the palette; risk levels retain text labels so color is not the only signal.

## 3. Production-style local run: one terminal

This builds an optimized static website and serves it through FastAPI.

```powershell
./start.ps1 -Port 8002
```

Open **http://localhost:8002**. If dependencies have not yet been installed, use `./start.ps1 -Setup -Port 8002`.

**Changes are not automatically rebuilt in this mode.** Stop with Ctrl+C, save your edits, and rerun `./start.ps1 -Port 8002`, then refresh the page. Backend changes also need a restart.

If PowerShell's script policy prevents `.ps1` files from running, use the individual commands below instead of changing your machine's policy:

```powershell
npm.cmd --prefix frontend run build
./.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

Do not use `npm run preview` as the full-stack server: it does not automatically provide the development API proxy. Use Vite dev mode or the FastAPI production-style run above.

## 4. Verify a fix

```powershell
$env:PYTHONPATH = 'backend'
./.venv/Scripts/python.exe -m pytest backend/tests -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

For consistent formatting:

```powershell
npm.cmd --prefix frontend run format
./.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
./.venv/Scripts/python.exe -m black backend/app backend/tests
```

Check the browser's Console/Network panels and both terminal logs. Confirm city switching, charts, mobile layout, and the feature you changed. A successful `/health` response verifies the process, **not** the upstream providers.

## 5. OpenAQ timeout: diagnose before changing the key

The API key authenticates an account; it is not tied to the computer where you obtained it. You can use the existing key in this computer's `.env`. An invalid key normally yields an HTTP **401** response. A connection timeout happens before a useful HTTP response and does not tell us whether the key is valid.

From the root folder:

```powershell
./diagnose.ps1
```

Or, without running a PowerShell script:

```powershell
$env:PYTHONPATH = 'backend'
./.venv/Scripts/python.exe -m app.diagnostics
```

The report checks DNS, an authenticated small OpenAQ request, and a separate weather request. It prints no API key, proxy credentials, or response body. Exit code 0 means both HTTPS requests returned 200; 1 means something needs attention. Diagnostics succeeding does not guarantee a city has current PM2.5 and PM10 coverage.

| Report | Meaning / next step |
| --- | --- |
| `openaq_key_configured: false` | Set `OPENAQ_API_KEY` in the root `.env`, then restart the backend. |
| DNS `ok: false` | The hostname cannot be resolved. Check the network/DNS service or ask the network administrator. |
| `connect_timeout` | The connection did not complete. Compare the same diagnostic on another permitted network (for example, your personal hotspot). If it succeeds there, ask the current network administrator to check the route/filter/proxy for `api.openaq.org:443`. |
| `connect_error` with DNS working | Check HTTPS connectivity, system time, certificate trust and any required proxy. |
| `read_timeout` | The server connection succeeded but the response was too slow. Retry later; if consistent, increase the read timeout as shown below. |
| `proxy_error` | Verify your organization's approved proxy configuration. Do not remove or bypass a required proxy. |
| `certificate_error` | Check system time and the approved CA configuration. Keep HTTPS certificate verification enabled. |
| HTTP 401 | Check the key/account in OpenAQ Explorer, save the correct key in `.env`, and restart the API. |
| HTTP 403 | The provider denied access. Check account restrictions or contact OpenAQ; this is not fixed by simply increasing a timeout. |
| HTTP 429 | Wait for the quota reset. Avoid repeated Refresh clicks or retry loops. |
| HTTP 502 / 503 / 504 | Possible upstream service issue. Retry later; the app makes only a bounded transient retry. |
| HTTP 200, but “no station” in the app | Connectivity works; recent paired pollutant coverage is missing. Try another city. This is a data-availability issue. |

### A useful comparison

1. Run diagnostics on this computer and on the other computer where you used the API.
2. If both fail on the same network, investigate that network or the provider.
3. If only this computer fails, compare approved proxy settings, Python environment, certificate trust and firewall/application rules.
4. If a permitted alternative network works, share the safe diagnostic report with the current network administrator. There is no need to turn off the firewall or share the key.

Optional read-only Windows checks:

```powershell
Resolve-DnsName api.openaq.org
Test-NetConnection api.openaq.org -Port 443
curl.exe --connect-timeout 8 --max-time 20 -I https://api.openaq.org
```

An HTTP response from the last command (even 401/403/404/405) demonstrates that HTTPS reached a server. That root/HEAD check does not validate the API key or a data endpoint. A TCP success alone does not prove TLS or HTTP works.

### Timeout configuration

Defaults (used even when these lines are absent from `.env`):

```dotenv
PROVIDER_CONNECT_TIMEOUT_SECONDS=8
PROVIDER_READ_TIMEOUT_SECONDS=25
PROVIDER_RETRIES=1
```

For a confirmed slow response, try `PROVIDER_READ_TIMEOUT_SECONDS=45`, then restart the backend. `PROVIDER_RETRIES=1` means at most two attempts, with a short backoff, for transient connection/read errors or HTTP 502/503/504. Authentication failures and HTTP 429 are not automatically retried. These limits apply per provider request; initial collection performs several requests. Increasing timeouts will not repair blocked routing, a bad key, or missing station coverage.

HTTPX respects standard proxy environment variables. On a managed network, obtain the approved `HTTP_PROXY` / `HTTPS_PROXY` configuration from the administrator. Diagnose the cause rather than disabling TLS validation or network protections.

Sources: [OpenAQ authentication](https://docs.openaq.org/using-the-api/api-key), [401 errors](https://docs.openaq.org/errors/unauthorized), [rate limits](https://docs.openaq.org/using-the-api/rate-limits), [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/), [HTTPX proxies](https://www.python-httpx.org/advanced/proxies/).

## 6. Common local issues

| Symptom | Fix |
| --- | --- |
| Port already in use / WinError 10048 | Stop your previous server with Ctrl+C, or choose another API port and update `VAYU_API_TARGET` in the frontend terminal. Do not stop unrelated processes. |
| Vite proxy error / connection refused | Start the API first and ensure the target matches its port. |
| Changes do not appear on port 8001/8002 | You may be viewing a built copy. Use port 5173 in development, or rebuild/restart the production-style server. |
| `No module named app` | Use the documented `--app-dir backend`, or set `$env:PYTHONPATH = 'backend'` before `python -m app...`. |
| Virtual environment fails after copying to another computer | Create a new environment on that computer and reinstall requirements; virtual environments are not portable. |
| Map tiles or fonts fail | They are external resources. Check network access; the dashboard has local font fallbacks. |
| Live values do not change immediately | Successful collection is cached for ten minutes. The observation time is the provider's time, not the last Refresh click. |

To stop development mode, press **Ctrl+C in both terminals**. To stop the one-terminal production-style run, press **Ctrl+C in that terminal**.
# Quick start on this configured computer

**New operational workflow:** see [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md)
for direct AirNow ingestion, the opt-in `run-monitor.cmd` collector, persistent
alert acknowledgements and the budget-constrained scenario planner.

The live pipeline now supports 42 Indian cities and explicitly labelled CAMS
regional forecasts when station coverage is incomplete. Read
[RESILIENT_FORECASTING.md](docs/RESILIENT_FORECASTING.md) for model selection,
source labels, saved data, operational response and remaining validation work.

Double-click `run-vayu.cmd` in the project folder. It opens separate backend
(port 8002) and frontend (port 5173) terminal windows. Once both report that they
are ready, open http://127.0.0.1:5173 and select **Live data**. Keep both windows
open. Stop them with Ctrl+C before launching again. These launchers use the
existing `.venv`, `frontend/node_modules`, and `.env`; they do not replace your key.

If live data fails, double-click `check-live-data.cmd`. Wait for its report and
share the output, which omits your API key. A successful OpenAQ check establishes
authentication and connectivity; station availability and usable training history
are checked separately by the application. Never share `.env` itself.

For separate starts, use `run-backend.cmd` and `run-frontend.cmd`. Frontend source
edits refresh automatically, and backend Python edits restart the development
server. After editing `.env`, restart the backend manually.
