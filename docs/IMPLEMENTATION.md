# PDF requirements and implementation

The supplied VAYU.pdf is a proposed system specification, not evidence of measured project outcomes. This implementation keeps the existing Vayu Health identity while implementing that proposal.

| PDF requirement | Implementation / boundary |
| --- | --- |
| 24-hour PM2.5 and PM10 forecast | Direct multi-output Extra Trees; explicit persistence fallback when continuous training history is insufficient |
| Ambient and weather input | OpenAQ v3 hourly sensor history joined to Open-Meteo weather in UTC; separate synthetic demo |
| Risk and alerts | In-app early-warning messages, audiences and validity windows; EPA 2024 PM-based hourly screening index, explicitly not official AQI |
| Hotspots / location map | OpenStreetMap with real station coordinates, concentration markers, source and age; no fabricated demo stations or source attribution |
| Forecast explanation | Global feature importance plus current-prediction grouped sensitivity relative to training medians |
| Industrial recommendations | Catalog-based operator review queue with rationale; no equipment control or assumed proven reduction |
| Optional scenario | User-adjustable mathematical concentration scaling; explicitly hypothetical |
| Forecast metrics | MAE, RMSE and R² against persistence on the same chronological holdout |
| Alert evaluation | Precision, recall, F1 and positive sample count; overlapping horizons are disclosed |
| Leakage prevention | Chronological training/calibration/test split, 24-origin purges, missing-hour exclusion |
| Uncertainty | Per-horizon calibration absolute-error bands when a model can be trained |

## Operational boundaries

- No external messages or alerts are sent. Review ticks last for the current browser session only.
- No measured compliance, health benefit, or pollution-reduction percentage is claimed.
- City weather is model/reanalysis data rather than station-measured meteorology.
- Models are station/window specific; seasonal or geographic transfer performance is not established.
- OpenAQ must be reachable from the API host and must provide sufficiently recent paired pollutants. A configured key alone does not establish provider availability.
- Real ingestion keeps missing values and rejects stale/invalid observations. The dashboard never presents synthetic data as a live fallback.
- Live collection stores aligned hourly CSVs. A successful collection is cached for ten minutes; use Refresh to check for updates.
- The local single-process app is suitable for demonstration and development. Public operation requires deployment-specific access controls, monitoring, durable ingestion scheduling, and source-license review.

## Verification performed

- Backend deterministic tests cover risk boundaries, sensor units, pagination, quality checks, provider errors, missing hours, request validation, a full demo forecast, and end-to-end mocked live collection with credential isolation.
- TypeScript checking and Vite production builds are run before delivery.
- Browser checks cover desktop/mobile layout, navigation, PM/history switching, operator review, and scenario slider behavior.
- Live API verification is reported separately in the delivery notes; mocked success is not treated as evidence of a real provider connection.
