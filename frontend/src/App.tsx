import { useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchForecast, fetchLocations } from "./api";
import type { Location, Snapshot } from "./types";
import StationMap from "./StationMap";
import Operations from "./Operations";
import Planner from "./Planner";
import Outcomes from "./Outcomes";
import Account from "./Account";
import Collections from "./Collections";
import DemoWorkflow from "./DemoWorkflow";

type Page =
  | "Overview"
  | "Forecasts"
  | "Station explorer"
  | "Health alerts"
  | "Action planner"
  | "Model & data";
const pages: { label: Page; icon: string }[] = [
  { label: "Overview", icon: "grid" },
  { label: "Forecasts", icon: "chart" },
  { label: "Station explorer", icon: "pin" },
  { label: "Health alerts", icon: "shield" },
  { label: "Action planner", icon: "layers" },
  { label: "Model & data", icon: "database" },
];
const paths: Record<string, string> = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  chart: "M3 3v18h18 M6 15l4-5 4 3 6-8",
  pin: "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z M12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z M12 8v5 M12 16h.01",
  layers: "m12 3 10 5-10 5L2 8l10-5Z M2 12l10 5 10-5 M2 16l10 5 10-5",
  database:
    "M20 6c0 2-16 2-16 0s16-2 16 0Z M4 6v12c0 3 16 3 16 0V6 M4 12c0 3 16 3 16 0",
  wind: "M3 8h12c5 0 5-6 1-6 M3 12h15c5 0 5 6 1 6 M3 16h7c4 0 4 6 0 5",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  download: "M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5",
  refresh: "M20 7v5h-5 M4 17v-5h5 M19 8a8 8 0 0 0-14-2 M5 16a8 8 0 0 0 14 2",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 1v3 M12 20v3 M1 12h3 M20 12h3 M4 4l2 2 M18 18l2 2 M4 20l2-2 M18 6l2-2",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 11v6 M12 7h.01",
  check: "m5 12 4 4L20 5",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v5l4 2",
};
function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.info} />
    </svg>
  );
}
const riskColor = (aqi: number) =>
  aqi <= 50
    ? "#546b41"
    : aqi <= 100
      ? "#78683e"
      : aqi <= 150
        ? "#675238"
        : aqi <= 200
          ? "#343d2c"
          : "#191b17";
function downloadCSV(data: Snapshot) {
  const lines = [
    [
      "timestamp_utc",
      "city",
      "mode",
      "source",
      "pm25_forecast_method",
      "pm10_forecast_method",
      "pm25_ug_m3",
      "pm10_ug_m3",
      "hourly_risk_index",
      "pm25_lower",
      "pm25_upper",
      "pm10_lower",
      "pm10_upper",
    ],
    ...data.forecast.map((r) => [
      r.timestamp,
      data.location.city,
      data.mode,
      data.data_source,
      data.provenance?.pm25.forecast_method || data.model.method,
      data.provenance?.pm10.forecast_method || data.model.method,
      r.pm25,
      r.pm10,
      r.aqi,
      r.pm25_lower ?? "",
      r.pm25_upper ?? "",
      r.pm10_lower ?? "",
      r.pm10_upper ?? "",
    ]),
  ];
  const csv = lines
    .map((row) =>
      row.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(","),
    )
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `vayu-${data.location.id}-${data.mode}-forecast.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export default function App() {
  const [page, setPage] = useState<Page>("Overview");
  const [cities, setCities] = useState<Location[]>([]);
  const [city, setCity] = useState("delhi");
  const [mode, setMode] = useState<"live" | "demo">("live");
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [partialStations, setPartialStations] = useState<Snapshot["stations"]>(
    [],
  );
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [pollutant, setPollutant] = useState<"pm25" | "pm10">("pm25");
  const [range, setRange] = useState<"forecast" | "history">("forecast");
  const [reduction, setReduction] = useState(15);
  const [query, setQuery] = useState("");
  const [reviewed, setReviewed] = useState<string[]>([]);
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [page]);
  useEffect(() => {
    const controller = new AbortController();
    fetchLocations(controller.signal)
      .then(setCities)
      .catch(() => {});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setPartialStations([]);
    setConnected(false);
    setData(null);
    fetchForecast(city, mode, controller.signal)
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") {
          setPartialStations(e.stations || []);
          setConnected(Boolean(e.connected));
        }
        if (e.name !== "AbortError")
          setError(
            e.message ||
              "Unable to reach the API. Check that the backend is running.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [city, mode, refresh]);
  const hour = (stamp: string) =>
    new Date(stamp).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: data?.location.timezone || "Asia/Kolkata",
    });
  const date = (stamp: string) =>
    new Date(stamp).toLocaleString("en-GB", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: data?.location.timezone || "Asia/Kolkata",
    });
  const peak = useMemo(
    () => data?.forecast.reduce((a, b) => (a.aqi > b.aqi ? a : b)),
    [data],
  );
  const elevated = data?.forecast.filter((r) => r.aqi >= 151).length || 0;
  const chart =
    range === "forecast"
      ? data?.forecast.map((r) => ({
          ...r,
          time: new Date(r.timestamp).getTime(),
          band:
            typeof r[`${pollutant}_lower`] === "number" && typeof r[`${pollutant}_upper`] === "number"
              ? [r[`${pollutant}_lower`], r[`${pollutant}_upper`]]
              : undefined,
        })) || []
      : data?.history.map((r) => ({ ...r, time: new Date(r.timestamp).getTime() })) || [];
  const scenario =
    data?.forecast.map((r) => ({
      time: hour(r.timestamp),
      baseline: r[pollutant],
      scenario: +(r[pollutant] * (1 - reduction / 100)).toFixed(1),
    })) || [];
  const forecastChart = (
    <article className="panel forecast-panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">LOOKING AHEAD</span>
          <h2>
            {range === "forecast"
              ? "24-hour pollution outlook"
              : "The last 72 hours"}
          </h2>
        </div>
        <div className="segmented">
          <button
            className={pollutant === "pm25" ? "selected" : ""}
            onClick={() => setPollutant("pm25")}
          >
            PM2.5
          </button>
          <button
            className={pollutant === "pm10" ? "selected" : ""}
            onClick={() => setPollutant("pm10")}
          >
            PM10
          </button>
        </div>
      </div>
      <div className="chart-top">
        <span>
          <i className="dot teal" />{" "}
          {pollutant === "pm25" ? "Fine particles" : "Coarse particles"}{" "}
          <small>µg/m³</small>
        </span>
        <select
          aria-label="Chart time range"
          value={range}
          onChange={(e) => setRange(e.target.value as "forecast" | "history")}
        >
          <option value="forecast">24h forecast</option>
          <option value="history">72h history</option>
        </select>
      </div>
      <p className="muted">{range === "forecast" ? `Method: ${data?.provenance?.[pollutant]?.forecast_method || data?.model.method}. A flat persistence forecast holds the latest measured concentration constant; it does not predict hourly changes.` : "Measured observations only. No history means the provider did not supply usable measurements."}</p>
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            key={`${city}-${range}-${pollutant}`}
            data={[...chart].sort((a,b)=>a.time-b.time)}
            margin={{ top: 10, right: 15, left: -22, bottom: 5 }}
          >
            <defs>
              <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#546b41" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#546b41" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              vertical={false}
              stroke="#dcccac"
              strokeDasharray="3 4"
            />
            <XAxis
              dataKey="time"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(value) => date(new Date(value).toISOString())}
              minTickGap={45}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "#546b41" }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "#546b41" }}
            />
            <Tooltip
              labelFormatter={(value) => date(new Date(Number(value)).toISOString())}
              formatter={(value, name) => [Array.isArray(value) ? `${value.join(" – ")} µg/m³` : `${value} µg/m³`, name]}
              contentStyle={{ borderRadius: 0, border: "1px solid #191b17" }}
            />
            <Area
              dataKey="band"
              isAnimationActive={false}
              name="Calibration band"
              stroke="none"
              fill="#99ad7a"
              fillOpacity={0.27}
            />
            <Area
              type="linear"
              isAnimationActive={false}
              dataKey={pollutant}
              name={pollutant === "pm25" ? "PM2.5" : "PM10"}
              stroke="#546b41"
              strokeWidth={2.5}
              fill="url(#area)"
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-caption">
        <span>
          <Icon name="clock" size={14} /> {data?.location.timezone}
        </span>
        <span>
          {range === "forecast"
            ? "Shaded range: calibration error band, when available"
            : data?.history.length ? "Gaps indicate missing observations" : "No measured history available; model output is not shown as observations"}
        </span>
      </div>
    </article>
  );
  const modelCard = (
    <article className="panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">BEHIND THE FORECAST</span>
          <h2>What the model uses</h2>
        </div>
        <span className="icon-box">
          <Icon name="layers" />
        </span>
      </div>
      {data?.model.importance.length ? (
        <div className="drivers">
          {data.model.importance.slice(0, 5).map((r) => (
            <div key={r.feature}>
              <div>
                <span>
                  {r.feature
                    .replaceAll("_", " ")
                    .replace("pm25", "PM2.5")
                    .replace("pm10", "PM10")}
                </span>
                <strong>{r.importance.toFixed(1)}%</strong>
              </div>
              <div className="track">
                <i style={{ width: `${r.importance}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">
          {data?.provenance ? "Independent forecasts use the selected pollutant's history; regional forecasts use CAMS atmospheric modelling. Feature attribution is not available for this combined outlook." : "Persistence repeats the latest concentration. No trained-model feature importance is available."}
        </p>
      )}
      <p className="fine-print">
        Global feature importance across both pollutants. Associations in the
        model do not establish causes.
      </p>
    </article>
  );
  const alertsPanel = (
    <article className="panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">EARLY WARNING</span>
          <h2>Health outlook</h2>
        </div>
        <Icon name="shield" />
      </div>
      {data?.alerts.map((alert) => (
        <div className={`alert-card ${alert.severity}`} key={alert.id}>
          <div className="alert-title">
            <i className="dot" />
            <strong>{alert.title.replace("AQI", "risk index")}</strong>
          </div>
          <p>{alert.message.replaceAll("AQI", "risk index")}</p>
          <div className="tags">
            {alert.populations
              .slice(0, page === "Health alerts" ? 5 : 3)
              .map((p) => (
                <span key={p}>{p}</span>
              ))}
          </div>
          {page === "Health alerts" && (
            <p className="fine-print">
              Forecast window: {date(alert.valid_from)} – {date(alert.valid_to)}
            </p>
          )}
        </div>
      ))}
      <p className="fine-print">
        Forecast guidance for awareness. Follow local authority advisories.
        Alerts are displayed here; no external notifications are sent.
      </p>
    </article>
  );
  const mapPanel = data && (
    <article className="panel map-panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">ON THE GROUND</span>
          <h2>Monitoring network</h2>
        </div>
        <span className="badge neutral">{data.stations.length} stations</span>
      </div>
      <StationMap data={data} />
      <div className="map-caption">
        <i className="dot teal" />
        <span>
          {data.mode === "demo"
            ? "City centre only · no fabricated stations"
            : `OpenAQ stations within 125 km · ${data.stations.filter((s) => Object.keys(s.readings).length).length} with recent PM readings · regional context, not city-wide exposure`}
        </span>
      </div>
    </article>
  );
  const actionsPanel = (
    <article className="panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">FROM INSIGHT TO ACTION</span>
          <h2>Industrial review queue</h2>
        </div>
        <span className="badge neutral">Human review</span>
      </div>
      <p className="muted">
        Suggested checks for local operators. These are not equipment commands
        or verified source-attribution findings.
      </p>
      <div className="action-list">
        {data?.interventions.map((action, i) => (
          <div className="action-item" key={action.id}>
            <span className="action-number">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <div className="action-title">
                <strong>{action.zone}</strong>
                <span
                  className={`badge ${action.compliance_priority === "high" ? "orange" : "neutral"}`}
                >
                  {action.compliance_priority} priority
                </span>
              </div>
              <p>{action.action}</p>
              <small>{action.rationale}</small>
            </div>
            <button
              className={`review-button ${reviewed.includes(action.id) ? "done" : ""}`}
              aria-label={`${reviewed.includes(action.id) ? "Unmark" : "Mark"} ${action.zone} reviewed`}
              title="Review status is local to this session"
              onClick={() =>
                setReviewed((v) =>
                  v.includes(action.id)
                    ? v.filter((x) => x !== action.id)
                    : [...v, action.id],
                )
              }
            >
              <Icon name="check" size={16} />
              {reviewed.includes(action.id) ? "Reviewed" : "Mark reviewed"}
            </button>
          </div>
        ))}
      </div>
      <p className="fine-print">
        Review ticks are temporary session notes, not measured compliance.{" "}
        {data?.impact_note}
      </p>
    </article>
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <a
          className="brand"
          aria-label="Vayu Health overview"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("Overview");
          }}
        >
          <span className="brand-mark">
            <Icon name="wind" size={29} />
          </span>
          <span>
            vayu<span className="brand-sub">AIR INTELLIGENCE</span>
          </span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map((item) => (
            <button
              key={item.label}
              aria-label={item.label}
              aria-current={page === item.label ? "page" : undefined}
              title={item.label}
              className={page === item.label ? "nav-item active" : "nav-item"}
              onClick={() => setPage(item.label)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.label === "Health alerts" && !!data?.alerts.length && (
                <small>{data.alerts.length}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="mission">
            <span className="mini-leaf">↗</span>
            <strong>
              Better air.
              <br />
              Earlier action.
            </strong>
            <p>Turning air quality data into a healthier tomorrow.</p>
            <span>CLIMATE & ENVIRONMENT</span>
          </div>
          <a
            className="docs-link"
            href="https://docs.openaq.org"
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="database" size={16} /> Powered by OpenAQ <span>↗</span>
          </a>
          <div className="operator">
            <span>VH</span>
            <div>
              <strong>Vayu Health</strong>
              <small>Decision support workspace</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{page}</strong>
          </div>
          <div className="topbar-right">
            <span className="system-status">
              <i
                className={`dot ${mode === "live" && data ? "teal" : "amber"}`}
              />
              {mode === "demo"
                ? "Demo environment"
                : data
                  ? data.provenance ? "Sources labelled below" : "OpenAQ connected"
                  : "Live environment"}
            </span>
            <span className="avatar">VH</span>
          </div>
        </header>
        <main>
          <section className="page-heading">
            <div>
              <div className="eyebrow">PREDICT. ALERT. ACT.</div>
              <h1>
                {page === "Overview" ? "A clearer picture of your air." : page}
              </h1>
              <p>
                {page === "Overview"
                  ? "Understand today. Prepare for tomorrow."
                  : (
                      {
                        Forecasts:
                          "Explore pollution trends and the next 24 hours.",
                        "Station explorer":
                          "See the observations behind your forecast.",
                        "Health alerts":
                          "Earlier awareness for people and communities.",
                        "Action planner":
                          "Support local decisions with transparent scenarios.",
                        "Model & data":
                          "Know where the data comes from and how predictions are evaluated.",
                      } as Record<string, string>
                    )[page]}
              </p>
            </div>
            <div className="heading-controls">
              <label className="select-wrap">
                <Icon name="pin" size={17} />
                <select
                  aria-label="Select city"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                >
                  {(cities.length
                    ? cities
                    : [
                        {
                          id: "delhi",
                          city: "Delhi",
                          country: "IN",
                        } as Location,
                      ]
                  ).map((c) => (
                    <option value={c.id} key={c.id}>
                      {c.city}, {c.country}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="button icon-button"
                aria-label="Refresh data"
                onClick={() => setRefresh((v) => v + 1)}
                disabled={loading}
              >
                <Icon name="refresh" />
              </button>
            </div>
          </section>
          <div className="toolbar">
            <div className="segmented mode-control">
              <button
                onClick={() => setMode("live")}
                className={mode === "live" ? "selected" : ""}
              >
                Live data
              </button>
              <button
                onClick={() => setMode("demo")}
                className={mode === "demo" ? "selected" : ""}
              >
                Demo
              </button>
            </div>
            <div className="toolbar-meta">
              {data && (
                <span>
                  {data.provenance ? "Forecast origin" : "Observed"}{" "}
                  {date(data.observed_at)} · {data.location.timezone}
                </span>
              )}
              <button
                className="text-button"
                onClick={() => data && downloadCSV(data)}
                disabled={!data}
              >
                <Icon name="download" size={16} /> Export forecast
              </button>
            </div>
          </div>
          {mode === "demo" && (
            <div className="notice">
              <Icon name="info" size={18} />
              <span>
                <strong>Demonstration mode.</strong> All readings and
                predictions are synthetic. Switch to live data for real station
                measurements.
              </span>
            </div>
          )}
          {error && (
            <section className="empty-state" role="alert">
              <span className="empty-icon">
                <Icon name="database" size={32} />
              </span>
              <h2>
                {connected
                  ? "Live observations · forecast unavailable"
                  : "Data connection needs attention"}
              </h2>
              <p>{error}</p>
              <div>
                <button
                  className="button primary"
                  onClick={() => setRefresh((v) => v + 1)}
                >
                  {connected ? "Refresh observations" : "Retry connection"}
                </button>
                {mode === "live" && (
                  <button className="button" onClick={() => setMode("demo")}>
                    Explore the demo
                  </button>
                )}
              </div>
              <p className="fine-print">
                Live data is never silently replaced with synthetic readings.
              </p>
            </section>
          )}
          {connected && partialStations.length > 0 && (
            <section
              className="panel"
              style={{ padding: 24, marginBottom: 24 }}
            >
              <h2>Latest available OpenAQ measurements</h2>
              <p>
                Individual monitoring stations, not city averages. Only readings
                from the last 24 hours are shown. Model training requires
                aligned history for both pollutants.
              </p>
              {partialStations
                .filter((s) => Object.keys(s.readings).length > 0)
                .map((s) => (
                  <article
                    key={s.id}
                    className="panel"
                    style={{ padding: 20, marginTop: 16 }}
                  >
                    <h3>{s.name}</h3>
                    <p>{s.provider}</p>
                    {(["pm25", "pm10"] as const).map((p) => (
                      <p key={p}>
                        <strong>{p === "pm25" ? "PM2.5" : "PM10"}: </strong>
                        {s.readings[p]
                          ? `${s.readings[p].value} µg/m³ · ${date(s.readings[p].observed_at)}`
                          : "No current measurement"}
                      </p>
                    ))}
                  </article>
                ))}
              {!partialStations.some(
                (s) => Object.keys(s.readings).length > 0,
              ) && <p>No current measurements in the checked stations.</p>}
            </section>
          )}
          {loading && (
            <section className="loading-state" role="status">
              <div className="loader" />
              <h2>
                {mode === "live"
                  ? "Collecting the air-quality picture"
                  : "Preparing the demonstration"}
              </h2>
              <p>
                Aligning hourly readings, checking data quality, and preparing a
                24-hour outlook.
              </p>
              <div className="skeleton-row">
                <i />
                <i />
                <i />
              </div>
            </section>
          )}
          {page === "Action planner" && <>{mode === "live" && <><Collections /><Account /></>}<Planner key={`${city}-${mode}`} city={city} mode={mode}/>{mode === "demo" ? <DemoWorkflow key={city}/> : <><Operations city={city}/><Outcomes city={city}/></>}</>}
          {data && !loading && (
            <>
              {(data.station?.distance_km || 0) > 25 && <div className="notice"><span>Regional station: {data.station?.name}, {data.station?.distance_km} km from the selected city centre. This is not a city-wide measurement.</span></div>}
              {data.provenance && (
                <section
                  className="panel"
                  style={{ padding: 24, marginBottom: 24 }}
                >
                  <span className="eyebrow">
                    {data.quality === "regional_model"
                      ? "REGIONAL MODEL OUTLOOK"
                      : "OBSERVATIONS + INDEPENDENT FORECASTS"}
                  </span>
                  <h2>Coverage gaps do not stop the outlook</h2>
                  <p>
                    Measured and modelled values are distinguished below.
                    Forecasts are provisional; regional estimates cannot resolve
                    street-level exposure or identify an industrial source.
                  </p>
                  {(["pm25", "pm10"] as const).map((p) => {
                    const source = data.provenance![p];
                    return (
                      <div
                        key={p}
                        style={{ borderTop: "1px solid", padding: "12px 0" }}
                      >
                        <strong>
                          {p === "pm25" ? "PM2.5" : "PM10"} ·{" "}
                          {source.current_kind}
                        </strong>
                        <p>
                          {source.station || source.current_source} ·{" "}
                          {date(source.current_at)}
                          {source.distance_km != null && ` · ${source.distance_km} km from city centre`}
                        </p>
                        <p>24-hour method: {source.forecast_method}</p>
                        {source.metrics && (
                          <p>
                            Untouched test MAE: tree {source.metrics.model.mae},
                            persistence {source.metrics.persistence.mae} µg/m³.{" "}
                            {source.metrics.train_rows} training /{" "}
                            {source.metrics.calibration_rows} calibration /{" "}
                            {source.metrics.test_rows} test origins;{" "}
                            {source.metrics.purge_hours}-hour gaps.
                          </p>
                        )}
                      </div>
                    );
                  })}
                  <p className="fine-print">
                    Regional data:{" "}
                    <a
                      href="https://open-meteo.com/en/docs/air-quality-api"
                      target="_blank"
                      rel="noreferrer"
                    >
                      CAMS Global / Open-Meteo
                    </a>{" "}
                    · approximately 45 km grid in India. No local accuracy or
                    calibrated uncertainty is claimed for CAMS.
                  </p>
                </section>
              )}
              {data.mode === "live" &&
                Date.now() - new Date(data.observed_at).getTime() >
                  3 * 3600000 && (
                  <div className="notice">
                    <Icon name="clock" size={18} />
                    <span>
                      <strong>Delayed observations.</strong> Forecast origin is{" "}
                      {date(data.observed_at)}. Part of this 24-hour outlook may
                      already have elapsed.
                    </span>
                  </div>
                )}
              {page === "Overview" && (
                <>
                  <div className="overview-top">
                    <article className="air-summary">
                      <div className="summary-top">
                        <span>
                          <i className="dot" />
                          {data.mode === "live"
                            ? data.provenance
                              ? "PROVISIONAL SCREENING"
                              : "LATEST COMPLETE HOUR"
                            : "DEMONSTRATION READING"}
                        </span>
                        <Icon name="wind" size={25} />
                      </div>
                      <div className="air-summary-content">
                        <div>
                          <p>{data.location.city} air quality</p>
                          <div className="big-index">
                            {data.aqi}
                            <span>
                              PM risk
                              <br />
                              index
                            </span>
                          </div>
                          <span className="risk-chip">{data.aqi_category}</span>
                        </div>
                        <div className="air-orbit">
                          <Icon name="wind" size={58} />
                        </div>
                      </div>
                      <div className="summary-footer">
                        <Icon name="info" size={15} />
                        <span>Hourly screening index · EPA PM breakpoints</span>
                      </div>
                    </article>
                    <article className="metric-card">
                      <span className="metric-icon">
                        <Icon name="layers" />
                      </span>
                      <p>Fine particles</p>
                      {data.provenance && (
                        <small>{data.provenance.pm25.current_kind}</small>
                      )}
                      <div className="metric-value">
                        {data.pm25}
                        <small>µg/m³</small>
                      </div>
                      <div className="metric-bottom">
                        <strong>PM2.5</strong>
                        <span>Particles ≤ 2.5 µm</span>
                      </div>
                      <div className="mini-bars">
                        {data.forecast.slice(0, 18).map((r, i) => (
                          <i
                            key={i}
                            style={{
                              height: `${Math.max(8, Math.min(45, (r.pm25 / Math.max(...data.forecast.map((v) => v.pm25))) * 40))}px`,
                            }}
                          />
                        ))}
                      </div>
                    </article>
                    <article className="metric-card">
                      <span className="metric-icon blue">
                        <Icon name="wind" />
                      </span>
                      <p>Particles up to 10 µm</p>
                      {data.provenance && (
                        <small>{data.provenance.pm10.current_kind}</small>
                      )}
                      <div className="metric-value">
                        {data.pm10}
                        <small>µg/m³</small>
                      </div>
                      <div className="metric-bottom">
                        <strong>PM10</strong>
                        <span>Particles ≤ 10 µm</span>
                      </div>
                      <div className="mini-bars blue">
                        {data.forecast.slice(0, 18).map((r, i) => (
                          <i
                            key={i}
                            style={{
                              height: `${Math.max(8, Math.min(45, (r.pm10 / Math.max(...data.forecast.map((v) => v.pm10))) * 40))}px`,
                            }}
                          />
                        ))}
                      </div>
                    </article>
                    <article className="metric-card outlook-card">
                      <span className="metric-icon orange">
                        <Icon name="clock" />
                      </span>
                      <p>Next 24h peak</p>
                      <div
                        className="metric-value"
                        style={{ color: riskColor(peak?.aqi || 0) }}
                      >
                        {peak?.aqi}
                        <small>index</small>
                      </div>
                      <div className="metric-bottom">
                        <strong>
                          {peak && hour(peak.timestamp)} local time
                        </strong>
                        <span>{elevated} hours at index ≥ 151</span>
                      </div>
                      <button
                        className="text-button"
                        onClick={() => setPage("Forecasts")}
                      >
                        Explore forecast <Icon name="arrow" size={16} />
                      </button>
                    </article>
                  </div>
                  <div className="two-column">
                    {forecastChart}
                    {alertsPanel}
                  </div>
                  <div className="weather-strip">
                    <span>
                      <Icon name="sun" /> Weather context
                    </span>
                    <div>
                      <strong>{data.weather.temperature_c}°C</strong>
                      <small>Temperature</small>
                    </div>
                    <div>
                      <strong>{data.weather.humidity_pct}%</strong>
                      <small>Humidity</small>
                    </div>
                    <div>
                      <strong>{data.weather.wind_speed_ms} m/s</strong>
                      <small>Wind · {data.weather.wind_direction_deg}°</small>
                    </div>
                    <div>
                      <strong>{data.weather.pressure_hpa} hPa</strong>
                      <small>Surface pressure</small>
                    </div>
                    <span className="weather-source">
                      {data.mode === "demo"
                        ? "Synthetic weather"
                        : "Open-Meteo"}
                    </span>
                  </div>
                  <div className="two-column">
                    {mapPanel}
                    {modelCard}
                  </div>
                  <div className="callout">
                    <div>
                      <span className="eyebrow">PREPARE, DON'T JUST REACT</span>
                      <h2>Turn the forecast into a plan.</h2>
                      <p>
                        Review suggested actions for{" "}
                        {data.location.industrial_zones.length} local industrial
                        areas.
                      </p>
                    </div>
                    <button
                      className="button primary"
                      onClick={() => setPage("Action planner")}
                    >
                      Open action planner <Icon name="arrow" size={17} />
                    </button>
                  </div>
                </>
              )}
              {page === "Forecasts" && (
                <>
                  {forecastChart}
                  <div className="two-column equal">
                    <article className="panel">
                      <span className="eyebrow">FORECAST METHOD</span>
                      <h2>{data.model.method}</h2>
                      <p className="muted">{data.model.note}</p>
                      {data.model.drivers?.length > 0 && (
                        <>
                          <h3>Current forecast sensitivity</h3>
                          <p className="fine-print">
                            Change in mean 24-hour{" "}
                            {pollutant === "pm25" ? "PM2.5" : "PM10"} compared
                            with replacing each feature group by its training
                            median, one group at a time. These effects are not
                            additive or causal.
                          </p>
                          <dl className="details">
                            {data.model.drivers.map((driver) => (
                              <div key={driver.label}>
                                <dt>{driver.label}</dt>
                                <dd>
                                  {driver[`${pollutant}_delta`] > 0 ? "+" : ""}
                                  {driver[`${pollutant}_delta`].toFixed(2)}{" "}
                                  µg/m³
                                </dd>
                              </div>
                            ))}
                          </dl>
                        </>
                      )}
                      <p className="fine-print">
                        Forecast origin: {date(data.observed_at)}. Predictions
                        use this origin; individual measurement times and
                        regional estimates are identified in the source
                        information.
                      </p>
                    </article>
                    {modelCard}
                  </div>
                  <article className="panel">
                    <div className="panel-head">
                      <h2>Hour-by-hour outlook</h2>
                      <button
                        className="text-button"
                        onClick={() => downloadCSV(data)}
                      >
                        <Icon name="download" size={16} /> Download CSV
                      </button>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Local time</th>
                            <th>PM2.5 · µg/m³</th>
                            <th>PM10 · µg/m³</th>
                            <th>PM risk index</th>
                            <th>Outlook</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.forecast.map((r) => (
                            <tr key={r.timestamp}>
                              <td>{date(r.timestamp)}</td>
                              <td>{r.pm25}</td>
                              <td>{r.pm10}</td>
                              <td>
                                <span
                                  className="table-index"
                                  style={{ color: riskColor(r.aqi) }}
                                >
                                  {r.aqi}
                                </span>
                              </td>
                              <td>{r.aqi_category}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </article>
                </>
              )}
              {page === "Station explorer" && (
                <>
                  {mapPanel}
                  <article className="panel">
                    <div className="panel-head">
                      <div>
                        <h2>Station observations</h2>
                        <p className="muted">
                          Recent measurements within 125 km. A hotspot is a
                          relative observation, not evidence of an emission
                          source.
                        </p>
                      </div>
                      <input
                        className="search"
                        aria-label="Search stations"
                        placeholder="Search stations…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </div>
                    {!data.stations.length ? (
                      <div className="inline-empty">
                        {data.mode === "demo" ? "No real monitoring stations are included in demo mode." : "No station metadata is available for this request. The regional outlook is shown separately from station measurements."}
                      </div>
                    ) : (
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Station / provider</th>
                              <th>PM2.5 · µg/m³</th>
                              <th>PM10 · µg/m³</th>
                              <th>Observation age</th>
                            </tr>
                          </thead>
                          <tbody>
                            {data.stations
                              .filter((s) =>
                                s.name
                                  .toLowerCase()
                                  .includes(query.toLowerCase()),
                              )
                              .map((s) => (
                                <tr key={s.id}>
                                  <td>
                                    <strong>{s.name}</strong>
                                    {s.selected && (
                                      <span className="badge neutral">
                                        Forecast station
                                      </span>
                                    )}
                                    <small>{s.provider}{s.distance_km != null && ` · ${s.distance_km} km from city centre`}</small>
                                  </td>
                                  <td>
                                    {s.readings.pm25?.value.toFixed(1) ??
                                      "Unavailable"}
                                  </td>
                                  <td>
                                    {s.readings.pm10?.value.toFixed(1) ??
                                      "Unavailable"}
                                  </td>
                                  <td>
                                    {Object.keys(s.readings).length
                                      ? `${Math.max(...Object.values(s.readings).map((r) => r.age_hours)).toFixed(1)} h`
                                      : "No recent PM data"}
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                        {!data.stations.some((s) =>
                          s.name.toLowerCase().includes(query.toLowerCase()),
                        ) && (
                          <p className="inline-empty">
                            No stations match this search.
                          </p>
                        )}
                      </div>
                    )}
                  </article>
                </>
              )}
              {page === "Health alerts" && (
                <div className="two-column equal">
                  {alertsPanel}
                  <article className="panel">
                    <span className="eyebrow">READING THE SIGNAL</span>
                    <h2>Understand the risk levels</h2>
                    <div className="risk-levels">
                      {[
                        [50, "Good"],
                        [100, "Moderate"],
                        [150, "Unhealthy for sensitive groups"],
                        [200, "Unhealthy"],
                        [300, "Very unhealthy"],
                        [500, "Hazardous"],
                      ].map(([n, label], i) => (
                        <div key={n}>
                          <i
                            className="dot"
                            style={{ background: riskColor(+n) }}
                          />
                          <strong>{label}</strong>
                          <span>
                            {[0, 51, 101, 151, 201, 301][i]}–{n}
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="fine-print">{data.aqi_method}</p>
                    <a
                      className="text-link"
                      href="https://www.airnow.gov/aqi/aqi-basics/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Read the EPA AQI guide ↗
                    </a>
                  </article>
                </div>
              )}
              {page === "Action planner" && (
                <>
                  
                  <article
                    className="panel"
                    style={{ padding: 24, marginBottom: 24 }}
                  >
                    <span className="eyebrow">OPERATOR RESPONSE WORKFLOW</span>
                    <h2>Verify, prepare, act, measure</h2>
                    {data.response_plan?.map((item, i) => (
                      <div key={item.step}>
                        <h3>
                          {i + 1}. {item.step}
                        </h3>
                        <p>{item.detail}</p>
                      </div>
                    ))}
                  </article>
                  {actionsPanel}
                  <article className="panel">
                    <div className="panel-head">
                      <div>
                        <span className="eyebrow">EXPLORE A POSSIBILITY</span>
                        <h2>What if concentrations were lower?</h2>
                      </div>
                      <span className="badge orange">
                        Hypothetical scenario
                      </span>
                    </div>
                    <p className="muted">
                      Scale forecast concentrations by a chosen percentage. This
                      is a mathematical sensitivity illustration, not an
                      emissions-response model or a promised intervention
                      effect.
                    </p>
                    <div className="scenario-control">
                      <label htmlFor="reduction">
                        Assumed concentration reduction{" "}
                        <strong>{reduction}%</strong>
                      </label>
                      <input
                        id="reduction"
                        type="range"
                        min="0"
                        max="50"
                        step="5"
                        value={reduction}
                        onChange={(e) => setReduction(+e.target.value)}
                      />
                      <div>
                        <span>0% · unchanged</span>
                        <span>50%</span>
                      </div>
                    </div>
                    <div className="segmented">
                      <button
                        className={pollutant === "pm25" ? "selected" : ""}
                        onClick={() => setPollutant("pm25")}
                      >
                        PM2.5
                      </button>
                      <button
                        className={pollutant === "pm10" ? "selected" : ""}
                        onClick={() => setPollutant("pm10")}
                      >
                        PM10
                      </button>
                    </div>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={scenario}>
                          <CartesianGrid vertical={false} stroke="#dcccac" />
                          <XAxis
                            dataKey="time"
                            minTickGap={45}
                            tick={{ fontSize: 11 }}
                          />
                          <YAxis unit="" tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Line
                            dataKey="baseline"
                            name="Forecast · µg/m³"
                            stroke="#99ad7a"
                            dot={false}
                            strokeDasharray="5 5"
                          />
                          <Line
                            dataKey="scenario"
                            name="Hypothetical · µg/m³"
                            stroke="#546b41"
                            strokeWidth={3}
                            dot={false}
                          />
                          <ReferenceLine y={0} stroke="#dcccac" />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                    <p className="fine-print">
                      No measured pollution reduction or health impact is
                      implied. Both lines inherit the uncertainty of the
                      forecast.
                    </p>
                  </article>
                </>
              )}
              {page === "Model & data" && (
                <>
                  <div className="two-column equal">
                    <article className="panel">
                      <span className="eyebrow">DATA PROVENANCE</span>
                      <h2>{data.data_source}</h2>
                      <dl className="details">
                        <div>
                          <dt>Data mode</dt>
                          <dd>{data.mode}</dd>
                        </div>
                        <div>
                          <dt>Forecast station</dt>
                          <dd>
                            {data.station?.name ||
                              (data.provenance
                                ? "Per-pollutant sources shown above"
                                : "Synthetic city series")}
                          </dd>
                        </div>
                        <div>
                          <dt>Complete hourly coverage</dt>
                          <dd>{data.coverage_pct}%</dd>
                        </div>
                        <div>
                          <dt>Collected at</dt>
                          <dd>{date(data.collected_at)}</dd>
                        </div>
                        <div>
                          <dt>Forecast origin</dt>
                          <dd>{date(data.observed_at)}</dd>
                        </div>
                      </dl>
                      {data.warnings.map((w) => (
                        <p className="fine-print" key={w}>
                          {w}
                        </p>
                      ))}
                    </article>
                    <article className="panel">
                      <span className="eyebrow">VALIDATION DESIGN</span>
                      <h2>Time moves forward. So do our tests.</h2>
                      <p className="muted">{data.model.note}</p>
                      <div className="split-bar">
                        <span>Train 65%</span>
                        <span>Calibrate 17%</span>
                        <span>Test 18%</span>
                      </div>
                      <p className="fine-print">
                        24-hour purges between splits prevent training targets
                        from overlapping the next split. Scores are aggregate
                        across horizons and are specific to this station and
                        data window.
                      </p>
                    </article>
                  </div>
                  <article className="panel">
                    <div className="panel-head">
                      <h2>Forecast performance</h2>
                      <span
                        className={`badge ${data.mode === "demo" ? "orange" : "neutral"}`}
                      >
                        {data.mode === "demo"
                          ? "Synthetic evaluation"
                          : "Station evaluation"}
                      </span>
                    </div>
                    {data.model.metrics ? (
                      <>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>Pollutant / model</th>
                                <th>MAE · µg/m³ ↓</th>
                                <th>RMSE · µg/m³ ↓</th>
                                <th>R² ↑</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(["pm25", "pm10"] as const).flatMap((p) =>
                                (["model", "persistence"] as const).map((m) => (
                                  <tr key={p + m}>
                                    <td>
                                      {p === "pm25" ? "PM2.5" : "PM10"} /{" "}
                                      {m === "model"
                                        ? "Extra Trees"
                                        : "Persistence baseline"}
                                    </td>
                                    <td>{data.model.metrics![p][m].mae}</td>
                                    <td>{data.model.metrics![p][m].rmse}</td>
                                    <td>{data.model.metrics![p][m].r2}</td>
                                  </tr>
                                )),
                              )}
                            </tbody>
                          </table>
                        </div>
                        <div className="score-grid">
                          {(["precision", "recall", "f1"] as const).map((k) => (
                            <div key={k}>
                              <span>Alert {k}</span>
                              <strong>
                                {(data.model.metrics!.alerts[k] * 100).toFixed(
                                  1,
                                )}
                                %
                              </strong>
                            </div>
                          ))}
                        </div>
                        <p className="fine-print">
                          Alert threshold: hourly PM risk index ≥ 151.{" "}
                          {data.model.metrics.alerts.positive_samples} positive
                          test horizon samples. Zero is reported when a metric
                          has no positive denominator; overlapping horizons are
                          not independent events.
                        </p>
                      </>
                    ) : (
                      <p className="inline-empty">
                        Insufficient continuous history to train and evaluate
                        the paired tree model. See per-pollutant methods above;
                        no paired accuracy claims are available.
                      </p>
                    )}
                  </article>
                  <article className="panel">
                    <h2>Standards, scope & limitations</h2>
                    <p className="muted">{data.aqi_method}</p>
                    <p className="muted">
                      Coverage differs by location. Predictions and calibration
                      bands are uncertain; industrial actions require local
                      validation. {data.impact_note}
                    </p>
                    <div className="source-links">
                      <a
                        href="https://docs.openaq.org"
                        target="_blank"
                        rel="noreferrer"
                      >
                        OpenAQ documentation ↗
                      </a>
                      <a
                        href="https://open-meteo.com/en/docs/historical-weather-api"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open-Meteo weather ↗
                      </a>
                      <a
                        href="https://www.airnow.gov/aqi/aqi-basics/"
                        target="_blank"
                        rel="noreferrer"
                      >
                        EPA risk guidance ↗
                      </a>
                    </div>
                  </article>
                </>
              )}
            </>
          )}
          <footer>
            <span>
              Vayu Health <i /> Air quality intelligence for earlier action.
            </span>
            <span>
              PS-1A · Climate & Environment <b>↗</b>
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
