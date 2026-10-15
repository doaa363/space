import React, { useState, useEffect } from 'react';
import { Satellite, Database, Activity, RefreshCw, Radio, ShieldCheck, AlertTriangle } from 'lucide-react';

export default function Navbar({ backendOnline, isDemo, onRefresh, loading, onSendSimulated }) {
  const [utcTime, setUtcTime] = useState(new Date().toUTCString());

  useEffect(() => {
    const timer = setInterval(() => {
      setUtcTime(new Date().toUTCString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-slate-800/80 px-4 py-3 sm:px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        
        {/* Brand & Mission Title */}
        <div className="flex items-center space-x-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 via-teal-500 to-cyan-400 p-0.5 shadow-lg shadow-emerald-500/20">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Satellite className="w-5 h-5 text-emerald-400 animate-pulse" />
            </div>
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
          </div>

          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                ClimCam
                <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  ISS EXP-71
                </span>
              </h1>
            </div>
            <p className="text-xs text-slate-400">
              Hyperspectral AI Ground Station &bull; East Africa Agriculture &bull; 1D-CNN INT8
            </p>
          </div>
        </div>

        {/* System Health Indicators & Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5 sm:gap-4 text-xs">
          {/* UTC Clock */}
          <div className="hidden lg:flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-300 font-mono">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span>{utcTime}</span>
          </div>

          {/* ISS Link Status */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-300">
            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span className="font-semibold">ISS Telemetry: Active</span>
          </div>

          {/* Backend / DB Status */}
          <div className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border ${
            backendOnline 
              ? 'bg-blue-950/40 border-blue-800/50 text-blue-300' 
              : 'bg-amber-950/30 border-amber-800/50 text-amber-300'
          }`}>
            <Database className="w-3.5 h-3.5" />
            <span>{backendOnline ? 'FastAPI + Mongo: Live' : 'Demo Mode (Offline)'}</span>
          </div>

          {/* Trigger Ingest Simulation */}
          <button
            onClick={onSendSimulated}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-medium shadow-md transition-all active:scale-95"
            title="Sends a new simulated ISS pass telemetry packet to the server"
          >
            <Satellite className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Simulate Pass</span>
          </button>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all disabled:opacity-50"
            title="Refresh Telemetry Stream"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>

      </div>
    </header>
  );
}
