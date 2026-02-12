"use client";

import { useEffect, useState } from "react";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  ReferenceLine, AreaChart, Area
} from "recharts";
import { CloudRain, AlertTriangle, TrendingUp, TrendingDown, History } from "lucide-react";

interface RainfallHistoryPanelProps {
  lat: number;
  lng: number;
}

export default function PlotRainfallHistoryPanel({ lat, lng }: RainfallHistoryPanelProps) {
  const [climatology, setClimatology] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [drought, setDrought] = useState<any>(null);
  const [anomaly, setAnomaly] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [climRes, histRes, droughtRes, anomalyRes] = await Promise.all([
          fetch(`/api/proxy?path=/eo/rainfall-climatology&lat=${lat}&lng=${lng}`),
          fetch(`/api/proxy?path=/eo/rainfall-history&lat=${lat}&lng=${lng}&years=30`),
          fetch(`/api/proxy?path=/eo/drought-analysis&lat=${lat}&lng=${lng}`),
          fetch(`/api/proxy?path=/eo/rainfall-anomaly&lat=${lat}&lng=${lng}`)
        ]);

        if (climRes.ok) setClimatology(await climRes.json());
        if (histRes.ok) setHistory(await histRes.json());
        if (droughtRes.ok) setDrought(await droughtRes.json());
        if (anomalyRes.ok) setAnomaly(await anomalyRes.json());

      } catch (error) {
        console.error("Failed to fetch rainfall data", error);
      } finally {
        setLoading(false);
      }
    };

    if (lat && lng) {
      console.log(`[PlotRainfallHistory] Fetching for ${lat}, ${lng}`);
      fetchData();
    } else {
        console.warn("[PlotRainfallHistory] Missing coordinates:", { lat, lng });
        setLoading(false);
    }
  }, [lat, lng]);

  if (loading) {
    return <div className="card h-[400px] w-full animate-pulse bg-slate-100 dark:bg-slate-800 border-none" />;
  }

  if (!history?.annual_records || !climatology?.monthly_normals_mm) {
     return (
        <div className="p-8 text-center text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30">
           <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-red-400" />
           <p className="font-semibold">Unable to load climate data.</p>
           <p className="text-xs mt-1 text-red-400 dark:text-red-300">Please check internet connection or try again later.</p>
           <p className="text-xs mt-2 text-slate-400 font-mono">Lat: {lat?.toFixed(2)}, Lng: {lng?.toFixed(2)}</p>
        </div>
     );
  }

  // Prepare chart data
  const chartData = history.annual_records.map((r: any) => ({
    year: r.year,
    rainfall: r.total_mm,
    normal: history.mean_annual_mm,
    status: r.classification
  }));

  const monthlyData = Object.entries(climatology.monthly_normals_mm).map(([month, val], idx) => ({
    month,
    normal: val,
    index: idx
  }));

  // Determine anomaly color
  const getAnomalyColor = (pct: number) => {
    if (pct < -30) return "text-red-600 dark:text-red-400";
    if (pct < -15) return "text-orange-500 dark:text-orange-400";
    if (pct > 30) return "text-blue-700 dark:text-blue-400";
    if (pct > 15) return "text-blue-500 dark:text-blue-400";
    return "text-green-600 dark:text-green-400";
  };

  return (
    <div className="space-y-6 fade-in">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400 mb-2">
            <CloudRain className="h-4 w-4" /> Current Anomaly
          </div>
          <div>
            <div className={`text-2xl font-bold ${getAnomalyColor(anomaly?.anomaly_pct || 0)}`}>
              {anomaly?.anomaly_pct > 0 ? "+" : ""}{anomaly?.anomaly_pct}%
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {anomaly?.status_ar || anomaly?.status} vs 30-year normal <br/>
              ({anomaly?.ytd_rainfall_mm}mm vs {anomaly?.expected_ytd_mm}mm expected)
            </p>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400 mb-2">
             <AlertTriangle className="h-4 w-4" /> Drought Risk
          </div>
          <div>
            <div className="text-2xl font-bold flex items-center gap-2">
              {drought?.risk_level === "high" ? (
                <span className="text-red-500 dark:text-red-400">High</span>
              ) : drought?.risk_level === "moderate" ? (
                <span className="text-orange-500 dark:text-orange-400">Moderate</span>
              ) : (
                <span className="text-green-500 dark:text-green-400">Low</span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Frequency: {drought?.drought_frequency}% ({drought?.drought_years_count} in 30 years)
            </p>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400 mb-2">
            <History className="h-4 w-4" /> Long-Term Trend
          </div>
          <div>
            <div className="text-2xl font-bold flex items-center gap-2">
              {history?.trend === "increasing" ? (
                <TrendingUp className="h-5 w-5 text-blue-500 dark:text-blue-400" />
              ) : history?.trend === "decreasing" ? (
                <TrendingDown className="h-5 w-5 text-red-500 dark:text-red-400" />
              ) : (
                <span className="text-slate-500 dark:text-slate-400 text-lg">Stable</span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {history?.trend_mm_per_year > 0 ? "+" : ""}{history?.trend_mm_per_year} mm/year <br/>
              30-year Avg: {history?.mean_annual_mm} mm
            </p>
          </div>
        </div>
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Historical Rainfall Chart */}
        <div className="card p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Rainfall History (1996-2025)</h3>
            <span className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-md">ERA5-Land</span>
          </div>
          <div className="h-[300px]">
             <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.2} stroke="#94a3b8" />
                  <XAxis 
                    dataKey="year" 
                    tick={{fontSize: 10, fill: '#94a3b8'}} 
                    interval={4} // Show every 5th year
                    stroke="#475569"
                  />
                  <YAxis tick={{fontSize: 10, fill: '#94a3b8'}} stroke="#475569" />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: '1px solid #334155', background: '#1e293b', color: '#f8fafc' }}
                  />
                  <ReferenceLine y={history?.mean_annual_mm} stroke="#fb923c" strokeDasharray="3 3" label={{ value: 'Avg', position: 'insideTopLeft', fontSize: 10, fill: '#fb923c' }} />
                  <Bar dataKey="rainfall" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
             </ResponsiveContainer>
          </div>
        </div>

        {/* Climatology Chart */}
        <div className="card p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Rainfall Climatology (Monthly Normals)</h3>
            <span className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-md">1991-2020</span>
          </div>
          <div className="h-[300px]">
             <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={monthlyData}>
                  <defs>
                    <linearGradient id="colorNormal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.2} stroke="#94a3b8" />
                  <XAxis dataKey="month" tick={{fontSize: 10, fill: '#94a3b8'}} stroke="#475569" />
                  <YAxis tick={{fontSize: 10, fill: '#94a3b8'}} stroke="#475569" />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: '1px solid #334155', background: '#1e293b', color: '#f8fafc' }}
                  />
                  <Area type="monotone" dataKey="normal" stroke="#0ea5e9" fillOpacity={1} fill="url(#colorNormal)" />
                </AreaChart>
             </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Drought Years List */}
      <div className="card p-4">
         <h3 className="text-sm font-semibold mb-3 text-slate-800 dark:text-slate-200">Identified Drought Years</h3>
         <div className="flex flex-wrap gap-2">
            {drought?.drought_years_list.map((year: number) => (
              <span key={year} className="px-2 py-1 text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 rounded-md border border-red-200 dark:border-red-900/50">
                {year}
              </span>
            ))}
            {drought?.drought_years_list.length === 0 && (
              <span className="text-sm text-slate-500 dark:text-slate-400">No severe drought years detected in analysis period.</span>
            )}
         </div>
      </div>
    </div>
  );
}
