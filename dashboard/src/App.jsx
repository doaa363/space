import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import CriticalAlertBanner from './components/CriticalAlertBanner';
import OverviewKPIs from './components/OverviewKPIs';
import BiophysicalCharts from './components/BiophysicalCharts';
import InteractiveMap from './components/InteractiveMap';
import TelemetryFeedTable from './components/TelemetryFeedTable';
import { checkBackendHealth, fetchTelemetry, transmitSimulationPacket, FALLBACK_TELEMETRY } from './services/api';
import { Satellite, ShieldCheck, Cpu, Database, CheckCircle2, AlertCircle } from 'lucide-react';

export default function App() {
  const [telemetryList, setTelemetryList] = useState(FALLBACK_TELEMETRY);
  const [activeRecord, setActiveRecord] = useState(FALLBACK_TELEMETRY[0]);
  const [backendOnline, setBackendOnline] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);

  // Show a temporary toast notification
  const showToast = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4500);
  };

  // Fetch telemetry and check system health
  const loadData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);

    try {
      // 1. Check health
      const health = await checkBackendHealth();
      setBackendOnline(health.online);

      // 2. Fetch telemetry
      const res = await fetchTelemetry({ limit: 25 });
      if (res.results && res.results.length > 0) {
        setTelemetryList(res.results);
        setIsDemo(res.isDemo ?? false);

        // Keep activeRecord up to date
        setActiveRecord((prev) => {
          if (!prev) return res.results[0];
          const exists = res.results.find((r) => r._id === prev._id);
          return exists || res.results[0];
        });
      }
    } catch (err) {
      console.error('Error fetching telemetry:', err);
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, []);

  // Initial load and periodic sync (every 25 seconds)
  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      loadData(true);
    }, 25000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Transmit simulated ISS pass packet to the FastAPI server
  const handleSendSimulated = async () => {
    setLoading(true);
    const newSceneId = `PASS-EA-${Math.floor(Math.random() * 900 + 100)}`;
    const randomVeg = Number((Math.random() * 35 + 40).toFixed(1));
    const randomHyd = Number((Math.random() * 20 + 10).toFixed(1));
    const randomDes = Number((100 - randomVeg - randomHyd - 8.0).toFixed(1));

    const simulatedPacket = {
      mission: `ISS-EXP-71-${newSceneId}`,
      sensor_id: "CLIMCAM-ISS-01",
      timestamp: new Date().toISOString(),
      scene_georeference: {
        center_lat: Number((Math.random() * 4.0 - 1.0).toFixed(4)),
        center_lon: Number((Math.random() * 4.0 + 34.0).toFixed(4)),
        pixel_resolution_m: 30.0
      },
      distribution: {
        Vegetation: randomVeg,
        Hydration: randomHyd,
        Desertification: Math.max(0, randomDes),
        Urban: 8.0
      },
      biophysical: {
        mean_ndvi: Number((randomVeg / 100 * 0.9 + 0.1).toFixed(3)),
        mean_ndwi: Number((randomHyd / 100 * 0.6 - 0.1).toFixed(3)),
        mean_ndre: Number((randomVeg / 100 * 0.6).toFixed(3))
      },
      alerts: randomDes > 30.0 ? [
        {
          severity: "CRITICAL",
          type: "RAPID_ARIDITY_SPIKE",
          message: "Soil moisture dropped sharply following recent thermal wind pass.",
          recommendation: "Activate agricultural relief groundwater canal pumps."
        }
      ] : [
        {
          severity: "INFO",
          type: "ROUTINE_MONITORING",
          message: "Standard multispectral telemetry captured within expected bounds.",
          recommendation: "No immediate mitigation required."
        }
      ],
      bandwidth: {
        raw_cube_mb: 489.4,
        payload_kb: 2.8,
        compression_ratio: 174785.0,
        bandwidth_saving_pct: 99.99
      }
    };

    try {
      if (backendOnline) {
        await transmitSimulationPacket(simulatedPacket);
        showToast(`🛰️ Telemetry packet [${newSceneId}] transmitted to FastAPI & stored in MongoDB!`, 'success');
        await loadData(false);
      } else {
        // Local simulation fallback
        const mockDoc = {
          _id: `mock-${Date.now()}`,
          ...simulatedPacket,
          has_critical: simulatedPacket.alerts[0].severity === 'CRITICAL',
          scene_location: {
            type: "Point",
            coordinates: [simulatedPacket.scene_georeference.center_lon, simulatedPacket.scene_georeference.center_lat]
          }
        };
        setTelemetryList((prev) => [mockDoc, ...prev]);
        setActiveRecord(mockDoc);
        showToast(`🛰️ Simulated local pass [${newSceneId}] injected into dashboard feed!`, 'info');
      }
    } catch (err) {
      showToast(`Simulation error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-slate-950">
      
      {/* Toast Notification Banner */}
      {notification && (
        <div className="fixed top-16 right-4 z-50 max-w-md animate-bounce">
          <div className={`p-4 rounded-xl border shadow-2xl flex items-center space-x-3 text-xs font-medium backdrop-blur-md ${
            notification.type === 'error'
              ? 'bg-rose-950/90 border-rose-600 text-rose-200'
              : notification.type === 'info'
              ? 'bg-cyan-950/90 border-cyan-600 text-cyan-200'
              : 'bg-emerald-950/90 border-emerald-600 text-emerald-200'
          }`}>
            {notification.type === 'error' ? (
              <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
        </div>
      )}

      {/* Main Top Navigation */}
      <Navbar
        backendOnline={backendOnline}
        isDemo={isDemo}
        onRefresh={() => loadData(false)}
        loading={loading}
        onSendSimulated={handleSendSimulated}
      />

      {/* Main Dashboard Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        
        {/* 1. Critical Alert Banner (High-Visibility Red/Amber Banner) */}
        <CriticalAlertBanner latestRecord={activeRecord} />

        {/* 2. Overview KPI Cards (Vegetation, Hydration, Desertification, ISS Compression) */}
        <OverviewKPIs latestRecord={activeRecord} />

        {/* 3. Charts & Biophysical Panel (Time-Series Area Chart + Donut Distribution) */}
        <BiophysicalCharts telemetryHistory={telemetryList} currentRecord={activeRecord} />

        {/* 4. Interactive Leaflet Map (East Africa ISS Ground Track & ROI Coordinates) */}
        <InteractiveMap
          telemetryList={telemetryList}
          activeRecord={activeRecord}
          onSelectRecord={(rec) => setActiveRecord(rec)}
        />

        {/* 5. Telemetry Downlink Packets Stream & Raw JSON Inspector */}
        <TelemetryFeedTable
          telemetryList={telemetryList}
          activeRecord={activeRecord}
          onSelectRecord={(rec) => setActiveRecord(rec)}
        />

      </main>

      {/* Aerospace Ground Station Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/90 px-4 py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Satellite className="w-4 h-4 text-emerald-500" />
            <span className="text-slate-400 font-semibold">ClimCam Earth Observation System</span>
            <span>&bull; ISS Expedition 71 Payload</span>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono">
            <span className="flex items-center gap-1 text-slate-400">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              Edge AI: 1D-CNN INT8 TFLite
            </span>
            <span className="flex items-center gap-1 text-slate-400">
              <Database className="w-3.5 h-3.5 text-emerald-400" />
              Backend: FastAPI + Motor Async
            </span>
            <span className="flex items-center gap-1 text-slate-400">
              <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
              WGS84 Coordinate Grid
            </span>
          </div>
        </div>
      </footer>

    </div>
  );
}
