import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { MapPin, Navigation, Compass, Crosshair, Layers } from 'lucide-react';

export default function InteractiveMap({ telemetryList, activeRecord, onSelectRecord }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);
  const roiPolygonRef = useRef(null);

  // Initialize Leaflet Map once
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Create map centered on East Africa
      const map = L.map(mapContainerRef.current, {
        center: [2.5, 34.0], // East Africa general center
        zoom: 5,
        zoomControl: false,
        attributionControl: false,
      });

      // Add Zoom control at top right
      L.control.zoom({ position: 'topright' }).addTo(map);

      // CartoDB Dark Matter tile layer
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 18,
        subdomains: 'abcd',
      }).addTo(map);

      // Layer group for telemetry markers
      const markersLayer = L.layerGroup().addTo(map);
      markersLayerRef.current = markersLayer;

      mapInstanceRef.current = map;
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Markers and Active Scene ROI when telemetryList or activeRecord changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();

    if (roiPolygonRef.current) {
      roiPolygonRef.current.remove();
      roiPolygonRef.current = null;
    }

    if (!telemetryList || telemetryList.length === 0) return;

    telemetryList.forEach((rec) => {
      const coords = rec.scene_location?.coordinates;
      if (!coords || coords.length !== 2) return;

      const [lon, lat] = coords;
      const isSelected = activeRecord?._id === rec._id;
      const hasCritical = rec.has_critical || rec.alerts?.some((a) => a.severity === 'CRITICAL');

      // Marker color
      const markerColor = hasCritical ? '#f43f5e' : isSelected ? '#10b981' : '#06b6d4';

      // Custom pulsing HTML icon
      const customIcon = L.divIcon({
        className: 'custom-leaflet-marker',
        html: `
          <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
            <div style="
              position: absolute;
              width: ${isSelected ? '28px' : '22px'};
              height: ${isSelected ? '28px' : '22px'};
              border-radius: 50%;
              background-color: ${markerColor};
              opacity: 0.35;
              animation: ping 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
            "></div>
            <div style="
              width: 14px;
              height: 14px;
              border-radius: 50%;
              background-color: ${markerColor};
              border: 2px solid #0f172a;
              box-shadow: 0 0 12px ${markerColor};
            "></div>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      const marker = L.marker([lat, lon], { icon: customIcon });

      const dist = rec.distribution || {};
      const bio = rec.biophysical || {};

      const popupContent = `
        <div style="font-family: inherit; min-width: 180px; padding: 4px;">
          <div style="font-size: 11px; font-weight: 700; color: ${markerColor}; text-transform: uppercase; margin-bottom: 2px;">
            ${hasCritical ? '⚠️ CRITICAL ALERT' : '🛰️ ISS Scene Capture'}
          </div>
          <div style="font-size: 13px; font-weight: 600; color: #ffffff; margin-bottom: 4px;">
            ${rec.sensor_id}
          </div>
          <div style="font-size: 10px; color: #94a3b8; font-family: monospace; margin-bottom: 8px;">
            Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 11px; margin-bottom: 6px;">
            <div style="background: rgba(16, 185, 129, 0.15); color: #34d399; padding: 4px 6px; border-radius: 4px;">
              Veg: <b>${(dist.Vegetation ?? dist.vegetation_pct ?? 0).toFixed(1)}%</b>
            </div>
            <div style="background: rgba(6, 182, 212, 0.15); color: #22d3ee; padding: 4px 6px; border-radius: 4px;">
              NDVI: <b>${(bio.mean_ndvi ?? 0).toFixed(3)}</b>
            </div>
          </div>
          <div style="font-size: 10px; color: #cbd5e1; border-top: 1px solid #334155; padding-top: 4px;">
            Mission: ${rec.mission}
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.on('click', () => {
        if (onSelectRecord) onSelectRecord(rec);
      });

      marker.addTo(markersLayer);

      // Draw bounding box / ROI Polygon for selected record
      if (isSelected) {
        const delta = 0.35; // ~38km field swath
        const bounds = [
          [lat - delta, lon - delta],
          [lat + delta, lon - delta],
          [lat + delta, lon + delta],
          [lat - delta, lon + delta],
        ];

        const polygon = L.polygon(bounds, {
          color: markerColor,
          weight: 2,
          fillColor: markerColor,
          fillOpacity: 0.15,
          dashArray: '4, 4',
        }).addTo(map);

        roiPolygonRef.current = polygon;
      }
    });

    // Center map on activeRecord smoothly
    if (activeRecord?.scene_location?.coordinates) {
      const [lon, lat] = activeRecord.scene_location.coordinates;
      map.flyTo([lat, lon], 7, { duration: 1.2 });
    }
  }, [telemetryList, activeRecord]);

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Compass className="w-4 h-4 text-cyan-400" />
            ISS Ground Track & Field Observation ROI (East Africa)
          </h2>
          <p className="text-xs text-slate-400">
            Real-time geospatial footprint & agricultural monitoring scenes from ISS orbit
          </p>
        </div>

        {/* Scene Quick Switcher */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 text-xs">
          {telemetryList?.slice(0, 4).map((rec) => {
            const isSelected = activeRecord?._id === rec._id;
            const coords = rec.scene_location?.coordinates || [0, 0];
            const isCrit = rec.has_critical;
            return (
              <button
                key={rec._id}
                onClick={() => onSelectRecord(rec)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border font-mono text-[11px] whitespace-nowrap transition-all ${
                  isSelected
                    ? isCrit
                      ? 'bg-rose-500/20 border-rose-500 text-rose-300 font-bold'
                      : 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-bold'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                <MapPin className={`w-3 h-3 ${isCrit ? 'text-rose-400' : 'text-emerald-400'}`} />
                <span>{rec.mission.replace('ISS-EXP-71-', '')}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Map Container */}
      <div className="relative w-full h-80 sm:h-96 rounded-xl overflow-hidden border border-slate-800 shadow-inner">
        <div ref={mapContainerRef} className="w-full h-full" />

        {/* Map Floating HUD Overlay */}
        <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 bg-slate-950/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-800 text-[11px] text-slate-300 font-mono shadow-lg">
          <Crosshair className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
          <span>Active Target: {activeRecord?.scene_location?.coordinates ? `[${activeRecord.scene_location.coordinates[1].toFixed(2)}°N, ${activeRecord.scene_location.coordinates[0].toFixed(2)}°E]` : 'Scanning'}</span>
        </div>

        <div className="absolute top-3 left-3 z-10 flex items-center gap-2 bg-slate-950/85 backdrop-blur-md px-2.5 py-1 rounded-lg border border-slate-800 text-[10px] text-slate-400">
          <Layers className="w-3 h-3 text-emerald-400" />
          <span>Swath: 38km Hyperspectral Field</span>
        </div>
      </div>

      {/* Map Footer Metadata */}
      <div className="mt-3 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between text-xs text-slate-400 gap-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-500" />
            <span>Optimal Crop Canopy</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-sm shadow-rose-500" />
            <span>Critical Aridity / Alert</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-sm shadow-cyan-500" />
            <span>Hydration Monitoring</span>
          </div>
        </div>

        <span className="font-mono text-slate-400">
          CartoDB Dark Matter &bull; WGS84 Projection
        </span>
      </div>
    </div>
  );
}
