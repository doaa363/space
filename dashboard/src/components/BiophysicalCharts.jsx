import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { Activity, PieChart as PieIcon, Info } from 'lucide-react';

export default function BiophysicalCharts({ telemetryHistory, currentRecord }) {
  const [activeMetric, setActiveMetric] = useState('all');

  // Format historical trend data from recent records
  const trendData = [...(telemetryHistory || [])]
    .reverse()
    .map((rec, index) => {
      const timeStr = rec.captured_at
        ? new Date(rec.captured_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : `Pass #${index + 1}`;
      return {
        name: timeStr,
        NDVI: Number((rec.biophysical?.mean_ndvi ?? 0).toFixed(3)),
        NDWI: Number((rec.biophysical?.mean_ndwi ?? 0).toFixed(3)),
        NDRE: Number((rec.biophysical?.mean_ndre ?? 0).toFixed(3)),
        mission: rec.mission,
        sensor: rec.sensor_id
      };
    });

  // Current field distribution for Donut Chart
  const dist = currentRecord?.distribution || {};
  const vegVal = dist.Vegetation ?? dist.vegetation_pct ?? 0;
  const hydVal = dist.Hydration ?? dist.hydration_pct ?? 0;
  const desVal = dist.Desertification ?? dist.desertification_pct ?? 0;
  const urbVal = dist.Urban ?? dist.urban_pct ?? 0;

  const donutData = [
    { name: 'Vegetation (غطاء نباتي)', value: Number(vegVal.toFixed(1)), color: '#10b981' }, // Emerald
    { name: 'Hydration (رطوبة)', value: Number(hydVal.toFixed(1)), color: '#06b6d4' },       // Cyan
    { name: 'Desertification (تصحر)', value: Number(desVal.toFixed(1)), color: '#f59e0b' }, // Amber
    { name: 'Urban (عمران)', value: Number(urbVal.toFixed(1)), color: '#8b5cf6' },          // Purple
  ];

  // Custom Glassmorphism Tooltip for AreaChart
  const CustomAreaTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-panel p-3 rounded-xl border border-slate-700/80 text-xs shadow-2xl">
          <p className="font-mono text-slate-300 font-semibold mb-2 border-b border-slate-800 pb-1">
            Timestamp: {label}
          </p>
          {payload.map((entry, idx) => (
            <div key={idx} className="flex items-center justify-between gap-4 py-0.5">
              <span className="flex items-center gap-1.5 font-medium" style={{ color: entry.color }}>
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                {entry.name}:
              </span>
              <span className="font-mono font-bold text-white">
                {entry.value}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      
      {/* 1. Time-Series Biophysical Trend (NDVI, NDWI, NDRE) - Spans 2 Cols */}
      <div className="lg:col-span-2 glass-panel rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
        <div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Biophysical Spectral Indicators (Time-Series)
              </h2>
              <p className="text-xs text-slate-400">
                Tracking vegetation vigor (NDVI), canopy chlorophyll (NDRE), and crop water index (NDWI)
              </p>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center space-x-1 p-1 bg-slate-900 rounded-lg border border-slate-800 text-[11px]">
              {['all', 'NDVI', 'NDWI', 'NDRE'].map((key) => (
                <button
                  key={key}
                  onClick={() => setActiveMetric(key)}
                  className={`px-2.5 py-1 rounded-md transition-all font-mono ${
                    activeMetric === key
                      ? 'bg-slate-800 text-white shadow-sm font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {key.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Area Chart Container */}
          <div className="h-64 sm:h-72 w-full mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorNdvi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorNdwi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorNdre" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0} />
                  </linearGradient>
                </defs>

                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
                <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis domain={[-0.3, 1.0]} stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip content={<CustomAreaTooltip />} />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />

                {(activeMetric === 'all' || activeMetric === 'NDVI') && (
                  <Area
                    type="monotone"
                    dataKey="NDVI"
                    stroke="#10b981"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#colorNdvi)"
                    name="NDVI (Vegetation Vigor)"
                  />
                )}

                {(activeMetric === 'all' || activeMetric === 'NDWI') && (
                  <Area
                    type="monotone"
                    dataKey="NDWI"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorNdwi)"
                    name="NDWI (Water Index)"
                  />
                )}

                {(activeMetric === 'all' || activeMetric === 'NDRE') && (
                  <Area
                    type="monotone"
                    dataKey="NDRE"
                    stroke="#a855f7"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorNdre)"
                    name="NDRE (Red Edge Chlorophyll)"
                  />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Informative Guidance Footer */}
        <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-cyan-400" />
            <span>Optimal Range: NDVI &gt; 0.5 (Healthy Biomass) | NDWI &gt; 0.0 (Adequate Soil Hydration)</span>
          </div>
          <span className="font-mono text-emerald-400 font-medium">Auto-synced</span>
        </div>
      </div>

      {/* 2. Donut Chart - 4-Class Semantic Breakdown */}
      <div className="glass-panel rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <PieIcon className="w-4 h-4 text-cyan-400" />
              Field Classification
            </h2>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
              ClimCam 1D-CNN
            </span>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            Current semantic distribution of 204 spectral bands in field ROI
          </p>

          {/* Pie Chart */}
          <div className="h-56 sm:h-60 w-full relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {donutData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke="#07090e" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(val) => [`${val}%`, 'Ratio']}
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '0.75rem',
                    color: '#f8fafc',
                    fontSize: '12px',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            {/* Center Summary Label */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-xs font-medium text-slate-400 uppercase">Canopy</span>
              <span className="text-xl font-extrabold font-mono text-emerald-400">
                {vegVal.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Legend Grid */}
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-800 text-xs">
          {donutData.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center space-x-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-slate-300 text-[11px] font-medium">{item.name.split(' ')[0]}</span>
              </div>
              <span className="font-mono font-bold text-white text-[11px]">{item.value}%</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
