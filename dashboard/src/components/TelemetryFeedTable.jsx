import React, { useState } from 'react';
import { Database, Radio, CheckCircle2, AlertOctagon, AlertTriangle, Eye, ChevronRight, X, Code2 } from 'lucide-react';

export default function TelemetryFeedTable({ telemetryList, activeRecord, onSelectRecord }) {
  const [inspectModalDoc, setInspectModalDoc] = useState(null);

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Radio className="w-4 h-4 text-emerald-400" />
            ISS Downlink Packets & Telemetry Stream
          </h2>
          <p className="text-xs text-slate-400">
            Real-time feed of ingested packets from the ISS sensor via FastAPI & MongoDB
          </p>
        </div>

        <span className="text-xs font-mono text-slate-400 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800 self-start sm:self-auto">
          {telemetryList?.length || 0} Ingested Records
        </span>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-900/90 text-slate-400 font-mono text-[11px] uppercase tracking-wider border-b border-slate-800">
            <tr>
              <th className="py-3 px-4">Sensor & Mission</th>
              <th className="py-3 px-4">Captured (UTC)</th>
              <th className="py-3 px-4">Semantic Breakdown</th>
              <th className="py-3 px-4">NDVI / NDWI</th>
              <th className="py-3 px-4">Alert Status</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {telemetryList?.map((rec) => {
              const isSelected = activeRecord?._id === rec._id;
              const dist = rec.distribution || {};
              const bio = rec.biophysical || {};
              const hasCrit = rec.has_critical;
              const hasWarn = rec.alerts?.some(a => a.severity === 'WARNING');

              const veg = dist.Vegetation ?? dist.vegetation_pct ?? 0;
              const hyd = dist.Hydration ?? dist.hydration_pct ?? 0;
              const des = dist.Desertification ?? dist.desertification_pct ?? 0;

              return (
                <tr
                  key={rec._id}
                  onClick={() => onSelectRecord(rec)}
                  className={`cursor-pointer transition-colors ${
                    isSelected ? 'bg-slate-800/80' : 'hover:bg-slate-900/50'
                  }`}
                >
                  {/* Sensor / Mission */}
                  <td className="py-3 px-4">
                    <div className="font-semibold text-white flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      {rec.sensor_id}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      {rec.mission}
                    </div>
                  </td>

                  {/* Timestamp */}
                  <td className="py-3 px-4 font-mono text-slate-300">
                    {rec.captured_at ? new Date(rec.captured_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'medium' }) : '-'}
                  </td>

                  {/* Distribution Mini Progress */}
                  <td className="py-3 px-4 min-w-[170px]">
                    <div className="flex items-center justify-between text-[11px] font-mono text-slate-300 mb-1">
                      <span className="text-emerald-400 font-semibold">{veg.toFixed(0)}% Veg</span>
                      <span className="text-cyan-400 font-semibold">{hyd.toFixed(0)}% Hyd</span>
                      <span className="text-amber-400 font-semibold">{des.toFixed(0)}% Des</span>
                    </div>
                    <div className="flex h-1.5 w-full rounded-full overflow-hidden bg-slate-950">
                      <div style={{ width: `${veg}%` }} className="bg-emerald-500" />
                      <div style={{ width: `${hyd}%` }} className="bg-cyan-500" />
                      <div style={{ width: `${des}%` }} className="bg-amber-500" />
                    </div>
                  </td>

                  {/* Biophysical Indices */}
                  <td className="py-3 px-4 font-mono">
                    <div className="text-white font-semibold">
                      NDVI: {(bio.mean_ndvi ?? 0).toFixed(3)}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      NDWI: {(bio.mean_ndwi ?? 0).toFixed(3)}
                    </div>
                  </td>

                  {/* Alert Status Badge */}
                  <td className="py-3 px-4">
                    {hasCrit ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">
                        <AlertOctagon className="w-3 h-3" />
                        CRITICAL
                      </span>
                    ) : hasWarn ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
                        <AlertTriangle className="w-3 h-3" />
                        WARNING
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        <CheckCircle2 className="w-3 h-3" />
                        OPTIMAL
                      </span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setInspectModalDoc(rec);
                      }}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all border border-slate-700"
                      title="Inspect Raw JSON Telemetry"
                    >
                      <Code2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Raw JSON Modal for Researchers */}
      {inspectModalDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="glass-panel w-full max-w-2xl rounded-2xl p-6 border border-slate-700 shadow-2xl flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2">
                <Code2 className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-white text-sm">
                  Raw ISS Telemetry Payload &bull; {inspectModalDoc.sensor_id}
                </h3>
              </div>
              <button
                onClick={() => setInspectModalDoc(null)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 font-mono text-xs p-4 rounded-xl bg-slate-950 border border-slate-900 text-emerald-400">
              <pre>{JSON.stringify(inspectModalDoc, null, 2)}</pre>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setInspectModalDoc(null)}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-all"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
