import React from 'react';
import { Sprout, Droplets, Sun, Layers, Cpu, TrendingUp, TrendingDown, ArrowUpRight } from 'lucide-react';

export default function OverviewKPIs({ latestRecord }) {
  if (!latestRecord) return null;

  const dist = latestRecord.distribution || {};
  const bio = latestRecord.biophysical || {};
  const bw = latestRecord.bandwidth || {};

  const vegPct = dist.Vegetation ?? dist.vegetation_pct ?? 0;
  const hydPct = dist.Hydration ?? dist.hydration_pct ?? 0;
  const desPct = dist.Desertification ?? dist.desertification_pct ?? 0;
  const urbPct = dist.Urban ?? dist.urban_pct ?? 0;

  const ndvi = bio.mean_ndvi ?? 0;
  const ndwi = bio.mean_ndwi ?? 0;

  const cards = [
    {
      title: "Vegetation Canopy Cover",
      arabicSubtitle: "الغطاء النباتي الحيوي",
      value: `${vegPct.toFixed(1)}%`,
      subvalue: `NDVI: ${ndvi.toFixed(3)}`,
      status: ndvi > 0.5 ? "Dense Canopy" : ndvi > 0.3 ? "Moderate Canopy" : "Sparse / Stressed",
      color: "emerald",
      icon: Sprout,
      glow: "glow-emerald",
      border: "border-emerald-500/30",
      accent: "from-emerald-500 to-teal-400",
      bgBadge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
      progress: Math.min(100, Math.max(0, vegPct)),
    },
    {
      title: "Soil & Crop Hydration",
      arabicSubtitle: "مستوى الرطوبة المائية",
      value: `${hydPct.toFixed(1)}%`,
      subvalue: `NDWI: ${ndwi.toFixed(3)}`,
      status: ndwi > 0.1 ? "Optimal Moisture" : ndwi > -0.05 ? "Normal Range" : "Severe Water Deficit",
      color: "cyan",
      icon: Droplets,
      glow: "glow-cyan",
      border: "border-cyan-500/30",
      accent: "from-cyan-500 to-blue-400",
      bgBadge: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
      progress: Math.min(100, Math.max(0, hydPct * 2)), // scaled
    },
    {
      title: "Desertification & Aridity",
      arabicSubtitle: "مؤشر التصحر والجفاف",
      value: `${desPct.toFixed(1)}%`,
      subvalue: desPct > 35 ? "⚠️ High Risk Zone" : "Within Baseline",
      status: desPct > 35 ? "Critical Alert" : desPct > 20 ? "Watch Status" : "Stable Buffer",
      color: desPct > 30 ? "rose" : "amber",
      icon: Sun,
      glow: desPct > 30 ? "glow-rose" : "glow-amber",
      border: desPct > 30 ? "border-rose-500/40" : "border-amber-500/30",
      accent: desPct > 30 ? "from-rose-500 to-red-400" : "from-amber-500 to-orange-400",
      bgBadge: desPct > 30 ? "bg-rose-500/15 text-rose-400 border-rose-500/30" : "bg-amber-500/15 text-amber-400 border-amber-500/30",
      progress: Math.min(100, Math.max(0, desPct)),
    },
    {
      title: "ISS Downlink Compression",
      arabicSubtitle: "نسبة ضغط التليمتري الفضائي",
      value: bw.compression_ratio ? `${(bw.compression_ratio / 1000).toFixed(0)}k : 1` : "175k : 1",
      subvalue: bw.bandwidth_saving_pct ? `${bw.bandwidth_saving_pct.toFixed(2)}% saved` : "99.99% saved",
      status: "TFLite INT8 Quantized",
      color: "purple",
      icon: Cpu,
      glow: "glow-cyan",
      border: "border-purple-500/30",
      accent: "from-purple-500 to-indigo-400",
      bgBadge: "bg-purple-500/15 text-purple-400 border-purple-500/30",
      progress: 99.99,
    }
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            className={`glass-panel rounded-2xl p-4 sm:p-5 border transition-all duration-300 hover:translate-y-[-2px] hover:border-slate-600 ${card.border}`}
          >
            {/* Top Bar: Icon + Arabic Label */}
            <div className="flex items-center justify-between mb-3">
              <div className={`p-2.5 rounded-xl bg-slate-900 border border-slate-800 ${card.glow}`}>
                <Icon className={`w-5 h-5 bg-gradient-to-r ${card.accent} bg-clip-text text-transparent`} />
              </div>
              <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${card.bgBadge}`}>
                {card.status}
              </span>
            </div>

            {/* Title & Arabic name */}
            <div className="mb-2">
              <div className="text-xs font-semibold text-slate-300 tracking-wide uppercase">
                {card.title}
              </div>
              <div className="text-[11px] text-slate-400 font-sans">
                {card.arabicSubtitle}
              </div>
            </div>

            {/* Primary Value */}
            <div className="flex items-baseline space-x-2 my-2">
              <span className="text-3xl font-extrabold font-mono tracking-tight text-white">
                {card.value}
              </span>
            </div>

            {/* Secondary stat / subvalue */}
            <div className="text-xs text-slate-400 font-mono flex items-center justify-between mb-3">
              <span>{card.subvalue}</span>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden border border-slate-800">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${card.accent} transition-all duration-700`}
                style={{ width: `${card.progress}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
