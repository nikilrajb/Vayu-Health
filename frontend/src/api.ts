import type { Location, Snapshot } from "./types";
const API = import.meta.env.VITE_API_URL || "";
async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}/api/v1${path}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(
      typeof body.detail === "string"
        ? body.detail
        : body.detail?.message || `Request failed (${response.status}). Please try again.`,
    );
    Object.assign(error, {stations: body.detail?.stations, connected: body.detail?.connected});
    throw error;
  }
  return response.json();
}
export const fetchLocations = (signal?: AbortSignal) =>
  get<Location[]>("/locations", signal);
export const fetchForecast = (
  city: string,
  mode: string,
  signal?: AbortSignal,
) =>
  get<Snapshot>(`/forecast/${encodeURIComponent(city)}?mode=${mode}`, signal);
