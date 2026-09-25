# PS-1A implementation checkpoint — 25 September 2026

## Delivered and tested

- Direct AirNow monitoring-site ingestion uses **RawConcentration**, verified
  units and UTC timestamps. AQI and NowCast/averaged Value fields are never used
  as hourly concentrations. Results are filtered to 125 km and 24-hour freshness.
  AirNow is a second source when the paired OpenAQ path is unavailable; it does
  not replace valid paired OpenAQ forecasts. Empty coverage preserves CAMS.
- AirNow histories accumulate locally by sensor for up to 45 days, with atomic
  file replacement. Long history is not fabricated from the first response.
- Independent pollutant models now join actual-time weather features when
  historical weather is available. Missing weather can retain a pollution-only
  path; the returned method states whether weather was used. Baselines remain
  explicit when training data is insufficient.
- A separate, opt-in monitor periodically collects forecasts and writes a
  durable SQLite check/alert ledger. Risk >=101 triggers a provisional alert.
  The same city/peak hour/severity is deduplicated; escalation creates a new alert.
- Action planner shows collection status and the persistent alert queue. An
  operator supplies their name and notes to acknowledge and resolve an alert.
  State transitions are append-only in the events table. No deletion endpoint
  exists. Acknowledgement must precede resolution.
- Scenario planner enumerates up to 12 candidate actions under an entered budget
  and hourly availability windows. It minimizes forecast hours with screening
  risk >=151, then summed risk, then cost. Percent effects are operator assumptions
  and combine multiplicatively; no local effect is inferred automatically.

## Run the operational workflow

1. Start the API/frontend with `run-vayu.cmd`.
2. Separately start `run-monitor.cmd`. Keep that terminal running. It checks
   Mumbai/Bengaluru every 15 minutes and survives individual collection failures.
   Stop with Ctrl+C. Do not launch multiple copies for the same cities.
3. Open Action planner → Refresh alert log. A successful check can produce zero
   alerts if the forecast does not meet the trigger; that is not an error.
4. Enter a responsible operator and an evidence/action note before changing state.
5. Enter feasible candidate actions and a budget to compare scenarios. Use the
   same cost units throughout and locally justified effectiveness assumptions.

Custom monitoring, in PowerShell from the project root:

```powershell
$env:PYTHONPATH='backend'
.venv/Scripts/python.exe -m app.monitor --cities delhi,mumbai,bangalore --interval 900
```

Use `--once` for a single collection pass. State lives in
`data/processed/operations.sqlite3`; preserve this file when backing up. Reading
`GET /api/v1/operations` returns the latest checks, 100 recent alerts, aggregate
status counts, and 200 recent audit events. It contains operator-entered names and
notes: keep the application bound to localhost. This prototype has no multi-user
authentication and is not ready to expose publicly.

## What remains unproven or unimplemented

- No email/SMS recipient or delivery service is configured. Monitoring creates
  local alerts only. It is not a Windows service and stops when its terminal or
  computer stops. There is no claim of 24/7 delivery.
- Site-specific assignments now record facility/zone, action, owner and deadline.
  The workflow is assigned → acknowledged → completed → verified, with evidence
  notes and a separate declared reviewer for verification. The metric is verified
  on-time completion divided by assignments due; it is undefined when none are
  due. This is local workflow compliance, not statutory compliance. Multi-user
  authentication and proof of reviewer identity remain future work.
- Measured-outcome review accepts a CSV associated with a completed assignment.
  Required columns: `period,site,timestamp,pm25_ugm3,pm10_ugm3`. Use before/after
  periods and intervention/reference sites. Both sites must have matching hourly
  UTC-aligned timestamps, continuous equal-length windows of at least 24 hours,
  and nonnegative concentrations. Timezone-naive timestamps, gaps and duplicates
  are rejected. The system saves the evidence CSV and calculated report locally.
  It reports observed high-risk station-hour reduction and a reference-adjusted
  percentage-point change. No real intervention dataset has been supplied yet;
  therefore there is no demonstrated impact. The operator must verify instrument
  quality, site comparability, intervention timing and potential confounding.
- Scenario reduction remains separate from measured outcomes. Do not present the
  optimizer's percentage as an achieved sustainability outcome.
- There is no calibrated industrial emissions-to-ambient-concentration model.
  The optimizer finds the best combination under the supplied assumptions, not
  the best physical intervention in the real world.
- Regional forecast skill still needs prospective local evaluation. The project
  is a working decision-support prototype, not a validated public-health system.

## Live verification at this checkpoint

The configured AirNow key returned HTTP 200. A Mumbai query returned zero rows;
a Los Angeles region query returned 456 records, including raw concentrations.
The key therefore does not eliminate geographical coverage gaps.

References: [AirNow](https://docs.airnowapi.org/) and the
[DOE ARM ACT AirNow implementation](https://arm-doe.github.io/ACT/_modules/act/discovery/airnow.html).
AirNow data are preliminary; use appropriate validated sources for regulatory work.
