"use client";

import { useEffect, useState } from "react";
import { OneSoilProfile, fetchOneSoilData } from "@/lib/onesoil-service";
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
  Filler
} from 'chart.js';

// Register ChartJS
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

interface OneSoilViewerProps {
  lat: number;
  lng: number;
  cropCode: string;
}

export default function OneSoilViewer({ lat, lng, cropCode }: OneSoilViewerProps) {
  const [data, setData] = useState<OneSoilProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeMetric, setActiveMetric] = useState<'ndvi' | 'ndmi'>('ndvi');

  useEffect(() => {
    async function loadData() {
      try {
        const result = await fetchOneSoilData(lat, lng, cropCode);
        setData(result);
      } catch (err) {
        console.error("OneSoil load failed", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [lat, lng, cropCode]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-400 bg-slate-900/50 rounded-xl border border-slate-700">
        <div className="animate-spin text-4xl mb-4">🛰️</div>
        <div className="animate-pulse">Acquiring OneSoil Satellite Uplink...</div>
      </div>
    );
  }

  if (!data) return <div className="p-4 bg-red-900/20 text-red-200 rounded">Satellite Data Unavailable</div>;

  const currentLayer = data.layers[0];

  // Chart Data
  const chartData = {
    labels: data.trend.map(d => d.date),
    datasets: [
      {
        label: activeMetric.toUpperCase(),
        data: data.trend.map(d => (d as any)[activeMetric]),
        borderColor: activeMetric === 'ndvi' ? '#34d399' : activeMetric === 'ndmi' ? '#60a5fa' : '#facc15', // EVI color
        backgroundColor: activeMetric === 'ndvi' ? 'rgba(52, 211, 153, 0.2)' : activeMetric === 'ndmi' ? 'rgba(96, 165, 250, 0.2)' : 'rgba(250, 204, 21, 0.2)', // EVI color
        fill: true,
        tension: 0.4,
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: { mode: 'index' as const, intersect: false },
    },
    scales: {
      y: {
        min: 0,
        max: 1,
        grid: { color: 'rgba(255,255,255,0.1)' }
      },
      x: {
        grid: { display: false }
      }
    }
  };

  return (
    <div className="fade-in space-y-6">
      
      {/* HEADER */}
      <div className="flex justify-between items-center mb-6">
         <div className="flex items-center gap-3">
             <img src="https://onesoil.ai/favicon.ico" alt="OneSoil" className="w-6 h-6 rounded" />
             <h3 className="text-lg font-bold text-white tracking-wide">OneSoil Intelligence</h3>
         </div>
         <span className="text-xs bg-slate-800 text-slate-400 px-3 py-1 rounded-full border border-slate-700">
            Updated: {currentLayer.date}
         </span>
      </div>

      {/* TOP ROW: MAP & ZONES */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* LATEST SATELLITE IMAGE */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4 relative overflow-hidden group">
              <div className="absolute top-4 left-4 z-10 bg-black/60 text-white text-xs px-2 py-1 rounded backdrop-blur">
                  Latest Sentinel-2 Pass
              </div>
              <div className="aspect-video w-full bg-slate-900 rounded-lg relative overflow-hidden flex items-center justify-center">
                   {/* Simulated Satellite View */}
                   <div style={{
                       width: '100%', height: '100%', 
                       background: `linear-gradient(rgba(0,0,0,0.1), rgba(0,0,0,0.1)), url('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/15/${Math.floor(lat)}/${Math.floor(lng)}')`,
                       backgroundSize: 'cover',
                       filter: activeMetric === 'ndvi' ? 'hue-rotate(90deg) contrast(1.2)' : 'none'
                   }}></div>
                   
                   {/* Overlay Text for Simulation */}
                   <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="text-white/20 text-6xl font-black tracking-tighter mix-blend-overlay">NDVI</div>
                   </div>
              </div>
              <div className="flex justify-between mt-4 text-sm">
                  <div className="text-slate-400">Cloud Cover: <b className="text-white">{currentLayer.cloudCover}%</b></div>
                  <div className="text-slate-400">Resolution: <b className="text-white">10m</b></div>
              </div>
          </div>

          {/* PRODUCTIVITY ZONES */}
          <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase mb-4 tracking-wider">Productivity Zones</h4>
              
              <div className="space-y-4">
                  {/* High Zone */}
                  <div className="space-y-1">
                      <div className="flex justify-between text-sm text-slate-300">
                          <span>High Vigor (Healthy)</span>
                          <span>{data.productivityZones.high}%</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500" style={{ width: `${data.productivityZones.high}%` }}></div>
                      </div>
                      <div className="text-xs text-slate-500">Requires standard maintenance.</div>
                  </div>

                  {/* Medium Zone */}
                  <div className="space-y-1">
                      <div className="flex justify-between text-sm text-slate-300">
                          <span>Medium Vigor</span>
                          <span>{data.productivityZones.medium}%</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div className="h-full bg-yellow-500" style={{ width: `${data.productivityZones.medium}%` }}></div>
                      </div>
                      <div className="text-xs text-slate-500">Monitor for potential N deficiency.</div>
                  </div>

                  {/* Low Zone */}
                  <div className="space-y-1">
                      <div className="flex justify-between text-sm text-slate-300">
                          <span>Low Vigor (Problematic)</span>
                          <span>{data.productivityZones.low}%</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div className="h-full bg-red-500" style={{ width: `${data.productivityZones.low}%` }}></div>
                      </div>
                       <div className="text-xs text-slate-500">Check for soil compaction or pests.</div>
                  </div>
              </div>
          </div>
      </div>

      {/* CHART SECTION */}
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-6">
          <div className="flex justify-between items-center mb-6">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Vegetation Index Trend (6 Months)</h4>
              <div className="flex bg-slate-700/50 rounded-lg p-1">
                  <button 
                    onClick={() => setActiveMetric('ndvi')}
                    className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${activeMetric === 'ndvi' ? 'bg-emerald-500 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                  >
                      NDVI
                  </button>
                  <button 
                    onClick={() => setActiveMetric('ndmi')}
                    className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${activeMetric === 'ndmi' ? 'bg-blue-500 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                  >
                      NDMI (Moisture)
                  </button>
              </div>
          </div>
          
          <div className="h-64 w-full">
              <Line data={chartData} options={chartOptions} />
          </div>
      </div>

    </div>
  );
}
