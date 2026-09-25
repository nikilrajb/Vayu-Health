# Vayu: forecast and respond when monitoring coverage breaks

## What was actually wrong

The Mumbai request reached OpenAQ successfully. The checked stations had no PM
readings within the last 24 hours. The original paired model required both PM2.5
and PM10, so valid API access still produced HTTP 503. Changing keys or increasing
timeouts could not repair this coverage gap.

The console's CancelledError occurred during server shutdown/reload; a later
“Application startup complete” means startup succeeded. The launcher now limits
reload watching to backend/app, excluding the virtual environment.

## Implemented decision path

1. Use the existing paired station model when fresh, aligned PM2.5, PM10 and
   weather history are available.
2. If that path fails, treat each pollutant independently. Select a fresh station
   for that pollutant; preserve its actual measurement timestamp and provider.
3. Retrieve up to 45 days of that sensor's measured hourly history. Train a
   single-pollutant, direct 30-horizon Extra Trees model from its own lags. It does
   not need the other pollutant or pretend that CAMS output is ground truth.
4. With at least 500 complete origins, split 60% train, 20% calibration, 20% test,
   removing 30 origins between adjacent sets. Choose trees versus persistence
   using calibration MAE only. Report both scores on the untouched test set.
   Forecast the next 24 hours relative to the current UTC hour, accounting for
   up to six hours of observation delay. Calibration residual bands are empirical,
   not guaranteed future coverage.
5. If station history cannot support that path, obtain a CAMS Global forecast
   through Open-Meteo. Display it as a regional model estimate. Station readings,
   where available, remain measured values; the forecast method is separately
   disclosed. CAMS estimates are never inserted into measured training history.
6. Generate a provisional screening outlook and operator response plan. Export
   includes the forecast method for each pollutant. Missing all usable sources
   still produces an explicit failure, never synthetic “live” data.

Successful results are cached for ten minutes. Historical station calls and
discovery are bounded. Freshest locations are checked first; stale location
metadata avoids unnecessary latest-reading calls. OpenAQ credentials are sent
only to OpenAQ. CAMS and weather use separate clients without the key.

## City coverage

42 Indian city centres are configured, including Bengaluru/Bangalore, Mumbai,
Delhi, Hyderabad, Chennai, Kolkata, Pune, Ahmedabad, Surat, Jaipur, Lucknow,
Kanpur, Nagpur, Indore, Bhopal, Patna, Chandigarh, Kochi, Thiruvananthapuram,
Coimbatore, Visakhapatnam, Vijayawada, Bhubaneswar, Guwahati, Ranchi, Raipur,
Noida, Gurugram, Ghaziabad, Faridabad, Agra, Varanasi, Amritsar, Ludhiana,
Jodhpur, Nashik, Vadodara, Rajkot, Madurai, Mysuru, Dehradun and Srinagar.
Listing a city does not promise a functioning station there. Coordinates are
city-centre search points, not exposure measurements or municipal boundaries.

## Resolving PM discrepancies

Do not use a universal PM10 = k × PM2.5 rule. Different times, instruments and
locations can yield an apparent PM2.5 > PM10 discrepancy. The application flags
this; it does not fabricate coarse mass or overwrite a real observation.
Independent outputs are not a chemically consistent joint particle-size model.
The combined index is therefore provisional when sources differ.

A useful next field experiment is a **mobile verification loop**: place a
co-located PM2.5/PM10 instrument where observations are missing or disagree with
the regional outlook. Co-locate with a reference instrument first, document
humidity/quality checks, and collect paired measurements before training a
local correction. This is a proposed experiment, not an implemented sensor feed.

Prioritise verification by (a) forecast severity, (b) absence/age of measurements,
and (c) observed/model disagreement. A severe estimate with poor coverage means
“verify urgently,” not “declare a particular factory responsible.”

## From forecast to action

The Action planner now provides four steps: verify evidence, prepare before the
forecast peak, inspect operations before selecting controls, and measure results.
Operators can review dust/material-handling controls and combustion maintenance.
No source attribution, legal compliance finding or causal reduction is claimed.

For an intervention trial, record the action, responsible operator and start/end
time; compare co-located PM readings before/after, wind conditions and an untreated
reference monitor. An observed fall alone is not proof of intervention impact.
The app's concentration slider remains a sensitivity illustration, not a causal
emissions model. Alerts are displayed in the app; external delivery is not wired.

## Evaluation and reproducibility

Measured history is saved under data/processed/*-independent-observations.csv.
Timestamped forecast snapshots, raw regional output and source metadata are saved
under data/processed/forecast_runs/. These allow subsequent comparison with
future observations. Prospective forecast skill has NOT yet been established;
historical test scores do not establish impact or future forecast accuracy.
Periodic collection is not scheduled automatically; collection occurs on request.

Run tests with `.venv/Scripts/python.exe -m pytest backend/tests -q` after setting
`PYTHONPATH=backend`. See RUN_GUIDE.md for startup and the full environment setup.

## Important limits and next engineering steps

- CAMS Global is approximately 45 km, with native three-hourly output exposed as
  hourly values by Open-Meteo. It cannot resolve a street, school or facility.
- The regional fallback has no local validation score or uncertainty band here.
- The current index uses EPA PM breakpoints as an hourly screening index. It is
  not India's official CPCB AQI and does not cover all regulated pollutants.
- Quality checks cannot guarantee a low-cost sensor's calibration.
- The discovery budget checks up to 16 recent stations within 125 km; this is not
  proof that every monitor in the metropolitan area is unavailable.
- Further work: archive issued forecasts on a schedule, validate against future
  measurements by horizon and season, then calibrate CAMS locally using only
  historical issued runs. Add authenticated CPCB/other feeds when available and
  an audited action/outcome ledger for field trials. Do not claim those exist now.

Source and attribution: [CAMS Global via Open-Meteo](https://open-meteo.com/en/docs/air-quality-api).
The free endpoint is for non-commercial evaluation; review provider terms for
commercial deployment. No additional key is needed for this prototype fallback.
