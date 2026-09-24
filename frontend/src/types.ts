export type Location = {
  id: string;
  city: string;
  country: string;
  latitude: number;
  longitude: number;
  timezone: string;
  industrial_zones: string[];
};
export type ForecastHour = {
  timestamp: string;
  horizon_h: number;
  pm25: number;
  pm10: number;
  aqi: number;
  aqi_category: string;
  pm25_lower: number | null;
  pm25_upper: number | null;
  pm10_lower: number | null;
  pm10_upper: number | null;
};
export type Station = {
  id: number;
  name: string;
  latitude: number | null;
  longitude: number | null;
  provider: string;
  selected: boolean;
  readings: Record<
    string,
    { value: number; observed_at: string; age_hours: number; sensor_id: number }
  >;
};
type Score = { mae: number; rmse: number; r2: number };
export type Snapshot = {
  location: Location;
  observed_at: string;
  collected_at: string;
  pm25: number;
  pm10: number;
  aqi: number;
  aqi_category: string;
  dominant_pollutant: string;
  mode: "live" | "demo";
  data_source: string;
  coverage_pct: number;
  warnings: string[];
  stations: Station[];
  station: Station | null;
  weather: {
    temperature_c: number;
    humidity_pct: number;
    wind_speed_ms: number;
    wind_direction_deg: number;
    pressure_hpa: number;
  };
  forecast: ForecastHour[];
  history: { timestamp: string; pm25: number | null; pm10: number | null }[];
  alerts: {
    id: string;
    title: string;
    message: string;
    severity: string;
    valid_from: string;
    valid_to: string;
    populations: string[];
  }[];
  interventions: {
    id: string;
    zone: string;
    action: string;
    rationale: string;
    compliance_priority: string;
    window_hours: number;
  }[];
  model: {
    method: string;
    note: string;
    importance: { feature: string; importance: number }[];
    drivers: { label: string; pm25_delta: number; pm10_delta: number }[];
    metrics: null | {
      pm25: { model: Score; persistence: Score };
      pm10: { model: Score; persistence: Score };
      alerts: {
        precision: number;
        recall: number;
        f1: number;
        positive_samples: number;
      };
      train_rows: number;
      validation_rows: number;
      test_rows: number;
      gap_hours: number;
      data_mode: string;
    };
  };
  aqi_method: string;
  impact_note: string;
};
