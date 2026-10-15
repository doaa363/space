import React from 'react';
import { AlertOctagon, AlertTriangle, ShieldAlert, ArrowRight, CheckCircle2 } from 'lucide-react';

export default function CriticalAlertBanner({ latestRecord }) {
  if (!latestRecord || !latestRecord.alerts || latestRecord.alerts.length === 0) {
    return null;
  }

  // Find critical alerts or warning alerts
  const criticalAlerts = latestRecord.alerts.filter(a => a.severity === 'CRITICAL');
  const warningAlerts = latestRecord.alerts.filter(a => a.severity === 'WARNING');
  const activeAlert = criticalAlerts[0] || warningAlerts[0];

  if (!activeAlert) {
    return null;
  }

  const isCritical = activeAlert.severity === 'CRITICAL';

  return (
    <div className={`w-full rounded-2xl p-4 sm:p-5 border transition-all duration-300 ${
      isCritical 
        ? 'bg-gradient-to-r from-rose-950/80 via-red-950/60 to-slate-900/90 border-rose-600/70 glow-rose' 
        : 'bg-gradient-to-r from-amber-950/80 via-yellow-950/60 to-slate-900/90 border-amber-600/70 glow-amber'
    }`}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        
        <div className="flex items-start space-x-3.5">
          <div className={`p-2.5 rounded-xl flex-shrink-0 ${
            isCritical ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40' : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
          }`}>
            {isCritical ? (
              <AlertOctagon className="w-6 h-6 animate-pulse" />
            ) : (
              <AlertTriangle className="w-6 h-6" />
            )}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold tracking-wider uppercase ${
                isCritical ? 'bg-rose-500 text-white shadow-sm shadow-rose-900' : 'bg-amber-500 text-slate-950'
              }`}>
                {activeAlert.severity} ALERT
              </span>
              <span className="text-xs font-mono font-medium text-slate-300">
                {activeAlert.type}
              </span>
              <span className="text-xs text-slate-400">
                &bull; Target: {latestRecord.mission} ({latestRecord.sensor_id})
              </span>
            </div>

            <p className="text-sm font-semibold text-white">
              {activeAlert.message}
            </p>

            {activeAlert.recommendation && (
              <div className="mt-2 text-xs text-rose-200/90 flex items-center gap-1.5 font-medium">
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                <span>Action Protocol: {activeAlert.recommendation}</span>
              </div>
            )}
          </div>
        </div>

        {/* Quick KPI stats from this alert scene */}
        <div className="flex items-center space-x-3 self-end md:self-center border-t md:border-t-0 md:border-l border-white/10 pt-3 md:pt-0 md:pl-4">
          <div className="text-right">
            <div className="text-[10px] text-slate-400 uppercase font-mono">NDWI Moisture</div>
            <div className={`text-base font-bold font-mono ${latestRecord.biophysical?.mean_ndwi < 0 ? 'text-rose-400' : 'text-cyan-400'}`}>
              {latestRecord.biophysical?.mean_ndwi?.toFixed(3) || '-'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-slate-400 uppercase font-mono">Desertification</div>
            <div className="text-base font-bold font-mono text-amber-400">
              {latestRecord.distribution?.Desertification?.toFixed(1) || latestRecord.distribution?.desertification_pct?.toFixed(1) || '0'}%
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
