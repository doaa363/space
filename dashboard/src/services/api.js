/**
 * ClimCam Ground Station — API Service
 * Connects React Frontend to the FastAPI Ground Station backend.
 * Provides fallback mock data with East Africa ISS passes when backend is offline.
 */

const API_BASE = 'http://127.0.0.1:8000/api';
const SENSOR_KEY = 'REDACTED_HISTORICAL_TOKEN';

// High-fidelity fallback telemetry data (East Africa ISS passes)
export const FALLBACK_TELEMETRY = [
  {
    _id: "telemetry-kenya-001",
    sensor_id: "CLIMCAM-ISS-01",
    mission: "ISS-EXP-71-AFRICA",
    captured_at: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    received_at: new Date(Date.now() - 1000 * 60 * 17).toISOString(),
    distribution: {
      Vegetation: 54.2,
      Hydration: 26.5,
      Desertification: 11.8,
      Urban: 7.5
    },
    biophysical: {
      mean_ndvi: 0.684,
      mean_ndwi: 0.215,
      mean_ndre: 0.432
    },
    alerts: [
      {
        severity: "INFO",
        type: "OPTIMAL_CANOPY",
        message: "Canopy health is robust across the western Rift Valley tea/coffee estates.",
        recommendation: "Maintain scheduled irrigation schedule; no stress markers detected."
      }
    ],
    has_critical: false,
    scene_location: {
      type: "Point",
      coordinates: [35.283, 0.514] // Eldoret / Rift Valley, Kenya
    },
    bandwidth: {
      raw_cube_mb: 485.2,
      payload_kb: 2.8,
      compression_ratio: 177445.0,
      bandwidth_saving_pct: 99.99
    }
  },
  {
    _id: "telemetry-egypt-002",
    sensor_id: "CLIMCAM-ISS-01",
    mission: "ISS-EXP-71-AFRICA",
    captured_at: new Date(Date.now() - 1000 * 60 * 105).toISOString(),
    received_at: new Date(Date.now() - 1000 * 60 * 104).toISOString(),
    distribution: {
      Vegetation: 22.4,
      Hydration: 8.6,
      Desertification: 58.1,
      Urban: 10.9
    },
    biophysical: {
      mean_ndvi: 0.285,
      mean_ndwi: -0.165,
      mean_ndre: 0.178
    },
    alerts: [
      {
        severity: "CRITICAL",
        type: "DESERTIFICATION_ENCROACHMENT",
        message: "Significant soil moisture depletion detected in the desert-edge agricultural belt.",
        recommendation: "Deploy emergency drip irrigation and soil barrier shields immediately."
      },
      {
        severity: "WARNING",
        type: "LOW_HYDRATION",
        message: "NDWI plunged below threshold (-0.165) indicating critical root-zone water stress.",
        recommendation: "Increase reservoir release by 25% for the adjacent wheat sector."
      }
    ],
    has_critical: true,
    scene_location: {
      type: "Point",
      coordinates: [30.825, 29.845] // Western Nile Delta Fringe, Egypt
    },
    bandwidth: {
      raw_cube_mb: 492.0,
      payload_kb: 2.9,
      compression_ratio: 169655.0,
      bandwidth_saving_pct: 99.99
    }
  },
  {
    _id: "telemetry-uganda-003",
    sensor_id: "CLIMCAM-ISS-01",
    mission: "ISS-EXP-71-AFRICA",
    captured_at: new Date(Date.now() - 1000 * 60 * 195).toISOString(),
    received_at: new Date(Date.now() - 1000 * 60 * 194).toISOString(),
    distribution: {
      Vegetation: 68.7,
      Hydration: 21.3,
      Desertification: 4.2,
      Urban: 5.8
    },
    biophysical: {
      mean_ndvi: 0.742,
      mean_ndwi: 0.284,
      mean_ndre: 0.495
    },
    alerts: [
      {
        severity: "INFO",
        type: "HIGH_VIGOR",
        message: "Dense agricultural canopy and ample wetland moisture across Lake Victoria basin.",
        recommendation: "Monitor for potential fungal flare-ups given elevated humidity indices."
      }
    ],
    has_critical: false,
    scene_location: {
      type: "Point",
      coordinates: [32.582, 0.347] // Kampala / Entebbe Belt, Uganda
    },
    bandwidth: {
      raw_cube_mb: 480.5,
      payload_kb: 2.7,
      compression_ratio: 177963.0,
      bandwidth_saving_pct: 99.99
    }
  },
  {
    _id: "telemetry-tanzania-004",
    sensor_id: "CLIMCAM-ISS-01",
    mission: "ISS-EXP-71-AFRICA",
    captured_at: new Date(Date.now() - 1000 * 60 * 285).toISOString(),
    received_at: new Date(Date.now() - 1000 * 60 * 284).toISOString(),
    distribution: {
      Vegetation: 45.1,
      Hydration: 17.8,
      Desertification: 29.5,
      Urban: 7.6
    },
    biophysical: {
      mean_ndvi: 0.521,
      mean_ndwi: 0.045,
      mean_ndre: 0.345
    },
    alerts: [
      {
        severity: "WARNING",
        type: "SEASONAL_DRYING",
        message: "Moderate vegetation drying trend observed along northern savannas.",
        recommendation: "Verify groundwater pump schedules for cereal crops."
      }
    ],
    has_critical: false,
    scene_location: {
      type: "Point",
      coordinates: [36.682, -3.386] // Arusha Region, Tanzania
    },
    bandwidth: {
      raw_cube_mb: 488.1,
      payload_kb: 2.8,
      compression_ratio: 174321.0,
      bandwidth_saving_pct: 99.99
    }
  }
];

/**
 * Checks if the FastAPI backend is live and healthy
 */
export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET', signal: AbortSignal.timeout(2500) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return { online: true, data };
  } catch (err) {
    return { online: false, error: err.message };
  }
}

/**
 * Fetches historical telemetry records with optional filters
 */
export async function fetchTelemetry(params = {}) {
  const query = new URLSearchParams();
  if (params.page) query.append('page', params.page);
  if (params.limit) query.append('limit', params.limit || 20);
  if (params.status && params.status !== 'all') query.append('status', params.status);
  if (params.sensor_id) query.append('sensor_id', params.sensor_id);

  try {
    const res = await fetch(`${API_BASE}/telemetry?${query.toString()}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(3000)
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const data = await res.json();
    
    // If backend has no records yet, combine or fallback
    if (!data.results || data.results.length === 0) {
      return {
        results: FALLBACK_TELEMETRY,
        total: FALLBACK_TELEMETRY.length,
        isDemo: true
      };
    }
    return { ...data, isDemo: false };
  } catch (err) {
    console.warn('[ClimCam API] Backend unreachable, using cached/demo telemetry:', err.message);
    return {
      results: FALLBACK_TELEMETRY,
      total: FALLBACK_TELEMETRY.length,
      isDemo: true,
      error: err.message
    };
  }
}

/**
 * Transmits a simulated ISS telemetry packet to the live backend
 */
export async function transmitSimulationPacket(packet) {
  try {
    const res = await fetch(`${API_BASE}/telemetry`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Sensor-Key': SENSOR_KEY,
      },
      body: JSON.stringify(packet),
    });
    return await res.json();
  } catch (err) {
    throw err;
  }
}
