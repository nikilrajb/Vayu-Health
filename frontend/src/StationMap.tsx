import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Snapshot } from "./types";

export default function StationMap({ data }: { data: Snapshot }) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const map = L.map(element.current, { scrollWheelZoom: false }).setView(
      [data.location.latitude, data.location.longitude],
      10,
    );
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);
    if (!data.stations.length)
      L.circleMarker([data.location.latitude, data.location.longitude], {
        radius: 9,
        color: "#546b41",
        fillOpacity: 0.4,
      })
        .addTo(map)
        .bindTooltip(
          `${data.location.city} city centre · no demo monitoring stations`,
        );
    const bounds: L.LatLngTuple[] = [];
    data.stations.forEach((station) => {
      if (station.latitude === null || station.longitude === null) return;
      const position: L.LatLngTuple = [station.latitude, station.longitude];
      bounds.push(position);
      const pm = station.readings.pm25?.value;
      const marker = L.circleMarker(position, {
        radius: station.selected ? 11 : 8,
        color: "#fff",
        weight: 2,
        fillColor:
          pm === undefined
            ? "#dcccac"
            : pm > 55.4
              ? "#191b17"
              : pm > 35.4
                ? "#99ad7a"
                : "#546b41",
        fillOpacity: 0.95,
      }).addTo(map);
      const popup = document.createElement("div");
      popup.textContent = `${station.name}${station.selected ? " · forecast station" : ""}. PM2.5: ${pm === undefined ? "unavailable" : pm.toFixed(1) + " µg/m³"}. ${station.provider}`;
      marker.bindPopup(popup);
    });
    if (bounds.length)
      map.fitBounds(bounds, { padding: [35, 35], maxZoom: 12 });
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(element.current);
    return () => {
      observer.disconnect();
      map.remove();
    };
  }, [data]);
  return (
    <div
      ref={element}
      className="station-map"
      aria-label={`Monitoring stations around ${data.location.city}`}
    />
  );
}
