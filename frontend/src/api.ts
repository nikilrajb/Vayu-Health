import type { Location, Snapshot } from "./types";
const API = import.meta.env.VITE_API_URL || "";
async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API}/api/v1${path}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}). Please try again.`,
    );
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
