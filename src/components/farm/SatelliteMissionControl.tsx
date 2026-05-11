"use client";

import { useEffect, useState, useRef } from "react";
import { OneSoilProfile } from "@/lib/onesoil-service";
import { SatelliteProvider, fetchSatelliteData, getAvailableProviders, ProviderInfo } from "@/lib/satellite-providers";
import { calculateZones, generateRasterGrid } from "@/lib/satellite-providers/satellite-utils";
import dynamic from 'next/dynamic';
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartData
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const OpenSatelliteMap = dynamic(() => import("./OpenSatelliteMap"), {
    ssr: false,
    loading: () => <div className="w-full h-full bg-slate-900 animate-pulse rounded-lg border-2 border-slate-800" />
});

function latLonToTile(lat: number, lng: number, zoom: number) {
  const x = Math.floor((lng + 180) / 360 * Math.pow(2, zoom));
  const latRad = lat * Math.PI / 180;
  const y = Math.floor((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * Math.pow(2, zoom));
  return { x, y, z: zoom };
}

interface SatelliteMissionControlProps {
  lat: number;
  lng: number;
  cropCode: string;
  geoJson?: Record<string, unknown>;
}

const METRIC_CONFIG = [
  { id: 'none', label: 'True Color', isIndex: false },
  { id: 'false-color', label: 'False Color', isIndex: false },
  { id: 'nir-r-g', label: 'NIR / R / G', isIndex: false },
  { id: 'ndvi', label: 'NDVI', isIndex: true },
  { id: 'evi', label: 'EVI', isIndex: true },
  { id: 'savi', label: 'SAVI', isIndex: true },
  { id: 'moisture-index', label: 'Moisture Index', isIndex: true },
  { id: 'moisture-stress', label: 'Moisture Stress', isIndex: false },
  { id: 'agriculture', label: 'Agriculture', isIndex: false },
  { id: 'barren-soil', label: 'Barren Soil', isIndex: false },
];

export default function SatelliteMissionControl({ lat, lng, cropCode, geoJson }: SatelliteMissionControlProps) {
  const [data, setData] = useState<OneSoilProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeMetric, setActiveMetric] = useState<string>('ndvi');
  const [timelineIndex, setTimelineIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [currentProvider, setCurrentProvider] = useState<SatelliteProvider>('sentinel'); // Default to Sentinel now
  const [showProviderMenu, setShowProviderMenu] = useState(false);
  const [availableProviders, setAvailableProviders] = useState<ProviderInfo[]>([]);

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const tileZoom = 15; 
  const tile = latLonToTile(lat, lng, tileZoom);
  const tileUrl = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${tile.z}/${tile.y}/${tile.x}`;

  useEffect(() => {
    async function loadData() {
      try {
        const [result, providers] = await Promise.all([
          fetchSatelliteData(currentProvider, lat, lng, cropCode),
          getAvailableProviders()
        ]);
        setData(result);
        setAvailableProviders(providers);
        setTimelineIndex(Math.max(0, result.layers.length - 1));
      } catch (err) {
        console.error("Satellite data load failed", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [lat, lng, cropCode, currentProvider]);

  useEffect(() => {
    if (isPlaying && data) {
      timerRef.current = setInterval(() => {
        setTimelineIndex(prev => {
          if (prev >= data.layers.length - 1) return 0;
          return prev + 1;
        });
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isPlaying, data]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-24 bg-slate-900 border border-slate-800 rounded-xl">
        <div className="w-16 h-16 border-t-4 border-blue-500 rounded-full animate-spin mb-6"></div>
        <div className="text-blue-400 font-mono tracking-widest animate-pulse">ESTABLISHING UPLINK...</div>
      </div>
    );
  }

  if (!data) return null;

  const currentLayer = data.layers[timelineIndex] || data.layers[0];
  const activeConfig = METRIC_CONFIG.find(c => c.id === activeMetric);
  const isIndexLayer = activeConfig?.isIndex || false;

  const chartData: ChartData<"line"> = {
    labels: (data.trend || []).map(d => d.date),
    datasets: [
        {
          label: activeMetric.toUpperCase() + ' Index',
          data: (data.trend || []).map(d => {
            if (activeMetric === 'moisture-index' || activeMetric === 'moisture-stress') return (d as any).ndmi || 0;
            return (d as any)[activeMetric] || 0;
          }),
          borderColor: activeMetric === 'ndvi' ? '#10b981' : (activeMetric === 'ndmi' || activeMetric === 'moisture-index' || activeMetric === 'moisture-stress') ? '#3b82f6' : '#8b5cf6',
          backgroundColor: (context) => {
            const ctx = context.chart.ctx;
            const gradient = ctx.createLinearGradient(0, 0, 0, 200);
            gradient.addColorStop(0, activeMetric === 'ndvi' ? 'rgba(16, 185, 129, 0.4)' : 'rgba(59, 130, 246, 0.4)');
            gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
            return gradient;
          },
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: '#1e293b',
          pointBorderColor: '#fff',
          fill: true,
          tension: 0.3,
        }
    ]
  };

  return (
    <section className="font-sans antialiased text-left text-slate-900 dark:text-slate-100" dir="ltr">
      <div className="flex flex-col md:flex-row justify-between items-start mb-6 border-b border-slate-200 dark:border-slate-800 pb-4 gap-4">
        <div className="flex-1">
          <h2 className="text-2xl font-black tracking-tight flex items-center gap-3 text-slate-900 dark:text-white">
            <span className="text-blue-500 text-3xl">❖</span> SATELLITE INTELLIGENCE
          </h2>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
              <div className="relative">
                <button
                  onClick={() => setShowProviderMenu(!showProviderMenu)}
                  className="flex items-center gap-2 text-xs px-3 py-1.5 rounded transition-colors bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700"
                >
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  {availableProviders.find(p => p.id === currentProvider)?.name || currentProvider}
                  <span className="text-slate-500">▼</span>
                </button>
                {showProviderMenu && (
                  <div className="absolute top-full left-0 mt-1 rounded-lg shadow-xl z-[1000] min-w-[220px] overflow-hidden bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                    {availableProviders.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => {
                          setCurrentProvider(p.id);
                          setShowProviderMenu(false);
                          setLoading(true);
                        }}
                        disabled={!p.isConfigured}
                        className={`w-full text-left px-3 py-2 text-xs border-b border-slate-100 dark:border-slate-800 last:border-0 transition-colors
                          ${currentProvider === p.id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : 'hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300'}
                          ${!p.isConfigured ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        <div className="font-bold">{p.name}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {p.isConfigured ? p.dataTypes.slice(0, 4).join(', ') + '...' : 'Not Configured'}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <span className="text-sm uppercase tracking-widest font-mono text-slate-500 dark:text-slate-400">
                 {data.isSimulation ? 'Simulated' : 'Live'} • {lat.toFixed(4)}, {lng.toFixed(4)}
              </span>
              <button
                onClick={() => setLoading(true)}
                className="text-xs px-2 py-1 rounded transition-colors bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 hover:text-blue-500"
              >↻ Refresh</button>
          </div>
        </div>

        {/* METRICS GRID */}
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-1.5 w-full md:w-auto">
           {METRIC_CONFIG.map((m) => (
             <button
               key={m.id}
               onClick={() => setActiveMetric(m.id)}
               className={`py-1.5 px-2 text-[9px] font-bold rounded transition-all border
                  ${activeMetric === m.id 
                    ? 'bg-blue-600 text-white border-blue-500 shadow-md' 
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-transparent hover:border-slate-300 dark:hover:border-slate-600'}`}
             >
               {m.label}
             </button>
           ))}
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="relative bg-slate-950 rounded-lg overflow-hidden border border-slate-800 shadow-xl h-[400px]">
           <div className="absolute top-4 left-4 z-500 bg-slate-900/90 backdrop-blur text-white px-3 py-1.5 rounded-md border border-slate-700/50 shadow-lg font-mono text-xs flex items-center gap-2 pointer-events-none">
              <span className="text-slate-400">PASS DATE:</span>
              <span className="text-blue-400 font-bold">{currentLayer.date}</span>
           </div>

           <div className="absolute inset-0 flex">
               <div className="h-full relative overflow-hidden transition-all duration-500 w-full" style={{ width: compareMode ? '50%' : '100%' }}>
                   <OpenSatelliteMap
                      lat={lat}
                      lng={lng}
                      geoJson={geoJson}
                      metric={activeMetric as any}
                      avgValue={(isIndexLayer && currentLayer) ? ((currentLayer as any)[activeMetric === 'moisture-index' ? 'ndmi' : activeMetric] as number) : undefined}
                      provider={currentProvider}
                      date={currentLayer.date}
                      rasterPixels={generateRasterGrid(geoJson, activeMetric, (isIndexLayer && currentLayer) ? ((currentLayer as any)[(activeMetric === 'moisture-index' || activeMetric === 'moisture-stress') ? 'ndmi' : activeMetric] as number) : 0.5)}
                   />
                   <div className="absolute bottom-6 left-6 text-7xl font-black text-white/5 pointer-events-none select-none tracking-tighter z-10">
                      {activeMetric.toUpperCase()}
                   </div>
               </div>
           </div>
        </div>

        <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800 flex items-center gap-4 backdrop-blur-sm">
           <button onClick={() => setIsPlaying(!isPlaying)} className={`w-12 h-12 flex items-center justify-center rounded-full shadow-lg ${isPlaying ? 'bg-amber-500' : 'bg-blue-600'} text-white`}>
               <span className="text-xl">{isPlaying ? '⏸' : '▶'}</span>
           </button>
           <div className="flex-1">
              <div className="relative h-2 bg-slate-800 rounded-full mt-2">
                  <div className="absolute top-0 left-0 h-full bg-blue-500 rounded-full" style={{ width: `${(timelineIndex / Math.max(1, data.layers.length - 1)) * 100}%` }}></div>
                  <input type="range" min="0" max={Math.max(0, data.layers.length - 1)} value={timelineIndex} onChange={(e) => setTimelineIndex(Number(e.target.value))} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
              </div>
           </div>
           {isIndexLayer && (
           <div className="text-right pl-4 border-l border-slate-800 min-w-[100px]">
               <div className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">{activeMetric} Value</div>
               <div className="text-2xl font-mono font-bold text-emerald-400">
                  {((currentLayer as any)[(activeMetric === 'moisture-index' || activeMetric === 'moisture-stress') ? 'ndmi' : activeMetric] || 0).toFixed(2)}
               </div>
           </div>
           )}
        </div>

        {isIndexLayer && (() => {
          // Compute real vigor zones from trend data
          const trendVals = (data.trend || []).map(d => {
            if (activeMetric === 'moisture-index' || activeMetric === 'moisture-stress') return (d as any).ndmi || 0;
            return (d as any)[activeMetric] || 0;
          }).filter(v => v > 0);

          const low = trendVals.filter(v => v < 0.35).length;
          const mid = trendVals.filter(v => v >= 0.35 && v < 0.6).length;
          const high = trendVals.filter(v => v >= 0.6).length;
          const total = Math.max(low + mid + high, 1);
          const lowPct = Math.round((low / total) * 100);
          const midPct = Math.round((mid / total) * 100);
          const highPct = 100 - lowPct - midPct;

          // Compute trend direction
          const currentVal = ((currentLayer as any)[(activeMetric === 'moisture-index' || activeMetric === 'moisture-stress') ? 'ndmi' : activeMetric] || 0);
          const avgVal = trendVals.length > 0 ? trendVals.reduce((a, b) => a + b, 0) / trendVals.length : 0;
          const recentVals = trendVals.slice(-3);
          const earlyVals = trendVals.slice(0, 3);
          const recentAvg = recentVals.length > 0 ? recentVals.reduce((a, b) => a + b, 0) / recentVals.length : 0;
          const earlyAvg = earlyVals.length > 0 ? earlyVals.reduce((a, b) => a + b, 0) / earlyVals.length : 0;
          const trendDir = recentAvg > earlyAvg + 0.02 ? 'improving' : recentAvg < earlyAvg - 0.02 ? 'declining' : 'stable';

          // Generate real insights
          const insights: { text: string; type: 'info' | 'warn' | 'good' }[] = [];
          if (currentVal > 0.6) insights.push({ text: `Strong ${activeMetric.toUpperCase()} (${currentVal.toFixed(2)}) — healthy canopy detected.`, type: 'good' });
          else if (currentVal > 0.35) insights.push({ text: `Moderate ${activeMetric.toUpperCase()} (${currentVal.toFixed(2)}) — growth in progress.`, type: 'info' });
          else if (currentVal > 0) insights.push({ text: `Low ${activeMetric.toUpperCase()} (${currentVal.toFixed(2)}) — sparse canopy or bare soil.`, type: 'warn' });

          if (trendDir === 'improving') insights.push({ text: `Trend is improving (+${((recentAvg - earlyAvg) * 100).toFixed(0)}%) over the observation window.`, type: 'good' });
          else if (trendDir === 'declining') insights.push({ text: `Trend is declining (${((recentAvg - earlyAvg) * 100).toFixed(0)}%) — potential stress.`, type: 'warn' });
          else insights.push({ text: `Index values are stable across the observation window.`, type: 'info' });

          if (trendVals.length > 0) {
            const maxVal = Math.max(...trendVals);
            const minVal = Math.min(...trendVals);
            insights.push({ text: `Range: ${minVal.toFixed(2)} – ${maxVal.toFixed(2)} (${trendVals.length} observations).`, type: 'info' });
          }

          const insightStyles = {
            good: 'bg-emerald-500/8 border-emerald-500/15 text-emerald-400',
            warn: 'bg-amber-500/8 border-amber-500/15 text-amber-400',
            info: 'bg-indigo-500/8 border-indigo-500/15 text-indigo-400',
          };

          return (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-[#0B1015]/60 backdrop-blur-xl p-4 rounded-xl border border-white/5">
                <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Trend Analysis</h4>
                <div className="h-32">
                  <Line data={chartData} options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                      x: { ticks: { color: '#475569', font: { size: 8 } }, grid: { color: 'rgba(255,255,255,0.03)' } },
                      y: { ticks: { color: '#475569', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.03)' } },
                    },
                  }} />
                </div>
                <div className="flex items-center justify-between mt-2 text-[9px] text-slate-600 font-mono">
                  <span>{trendVals.length} obs</span>
                  <span>avg: {avgVal.toFixed(3)}</span>
                  <span className={trendDir === 'improving' ? 'text-emerald-500' : trendDir === 'declining' ? 'text-rose-500' : 'text-slate-400'}>
                    {trendDir === 'improving' ? '↑' : trendDir === 'declining' ? '↓' : '→'} {trendDir}
                  </span>
                </div>
              </div>

              <div className="bg-[#0B1015]/60 backdrop-blur-xl p-4 rounded-xl border border-white/5">
                <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Field Vigor Distribution</h4>
                <div className="flex h-3 rounded-full overflow-hidden bg-slate-800/50 mb-3">
                  {lowPct > 0 && <div style={{ width: `${lowPct}%` }} className="bg-rose-500/80 transition-all duration-500" />}
                  {midPct > 0 && <div style={{ width: `${midPct}%` }} className="bg-amber-500/80 transition-all duration-500" />}
                  {highPct > 0 && <div style={{ width: `${highPct}%` }} className="bg-emerald-500/80 transition-all duration-500" />}
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="text-lg font-mono font-bold text-rose-400">{lowPct}%</div>
                    <div className="text-[9px] text-slate-600 uppercase tracking-widest">Stressed</div>
                  </div>
                  <div>
                    <div className="text-lg font-mono font-bold text-amber-400">{midPct}%</div>
                    <div className="text-[9px] text-slate-600 uppercase tracking-widest">Moderate</div>
                  </div>
                  <div>
                    <div className="text-lg font-mono font-bold text-emerald-400">{highPct}%</div>
                    <div className="text-[9px] text-slate-600 uppercase tracking-widest">Healthy</div>
                  </div>
                </div>
                <div className="mt-3 pt-2 border-t border-white/5 text-[9px] text-slate-600 font-mono text-center">
                  Based on {total} temporal observations
                </div>
              </div>

              <div className="bg-[#0B1015]/60 backdrop-blur-xl p-4 rounded-xl border border-white/5">
                <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Automated Insights</h4>
                <div className="space-y-2">
                  {insights.map((ins, i) => (
                    <div key={i} className={`p-2 rounded-lg border text-[10px] leading-relaxed ${insightStyles[ins.type]}`}>
                      {ins.text}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })()}

        {activeMetric === 'nir-r-g' && (
           <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800 mt-4 backdrop-blur-sm">
              <h4 className="text-[11px] font-bold text-slate-400 uppercase mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  False Color Interpretation (NIR / Red / Green)
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="flex items-center gap-2 p-2 bg-slate-950/50 rounded border border-slate-800">
                      <div className="w-8 h-8 rounded bg-red-600 shadow-lg shadow-red-900/20 shrink-0"></div>
                      <div className="text-[10px] leading-tight">
                          <div className="text-red-400 font-bold">Bright Red</div>
                          <div className="text-slate-500">Healthy Crops (Biomass)</div>
                      </div>
                  </div>

                  <div className="flex items-center gap-2 p-2 bg-slate-950/50 rounded border border-slate-800">
                      <div className="w-8 h-8 rounded bg-pink-500 shadow-lg shadow-pink-900/20 shrink-0"></div>
                      <div className="text-[10px] leading-tight">
                          <div className="text-pink-400 font-bold">Pink / Magenta</div>
                          <div className="text-slate-500">Plastic Greenhouses</div>
                      </div>
                  </div>

                  <div className="flex items-center gap-2 p-2 bg-slate-950/50 rounded border border-slate-800">
                      <div className="w-8 h-8 rounded bg-amber-900 shadow-lg shadow-amber-900/20 shrink-0"></div>
                      <div className="text-[10px] leading-tight">
                          <div className="text-amber-600 font-bold">Brown</div>
                          <div className="text-slate-500">Bare Soil / Earth</div>
                      </div>
                  </div>

                  <div className="flex items-center gap-2 p-2 bg-slate-950/50 rounded border border-slate-800">
                      <div className="w-8 h-8 rounded bg-slate-400 shadow-lg shadow-slate-900/20 shrink-0"></div>
                      <div className="text-[10px] leading-tight">
                          <div className="text-slate-300 font-bold">Gray / Cyan</div>
                          <div className="text-slate-500">Buildings / Roads</div>
                      </div>
                  </div>

                  <div className="flex items-center gap-2 p-2 bg-slate-950/50 rounded border border-slate-800">
                      <div className="w-8 h-8 rounded bg-red-900 shadow-lg shadow-red-900/20 shrink-0"></div>
                      <div className="text-[10px] leading-tight">
                          <div className="text-red-800 font-bold">Dark Red</div>
                          <div className="text-slate-500">Vegetation Stress</div>
                      </div>
                  </div>
              </div>
           </div>
        )}
      </div>
    </section>
  );
}
