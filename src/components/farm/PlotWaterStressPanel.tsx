"use client";

import { useEffect, useState } from "react";
import { 
  ComposedChart, Bar, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from "recharts";
import { Droplets, Sun, AlertOctagon } from "lucide-react";

interface WaterStressPanelProps {
  lat: number;
  lng: number;
}

export default function PlotWaterStressPanel({ lat, lng }: WaterStressPanelProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [kc, setKc] = useState(1.0); // Crop Coefficient (default to mid-season)

  // Fetch Water Balance Data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Use proxy to avoid CORS
        const response = await fetch(`/api/proxy?path=/eo/water-balance&lat=${lat}&lng=${lng}&days_past=30&days_future=7`);
        if (response.ok) {
          const result = await response.json();
          setData(result);
        }
      } catch (error) {
        console.error("Failed to fetch water balance", error);
      } finally {
        setLoading(false);
      }
    };

    if (lat && lng) fetchData();
  }, [lat, lng]);

  if (loading) {
    return <div className="card h-[400px] w-full animate-pulse bg-gray-100" />;
  }

  if (!data || !data.records) {
      return (
         <div className="p-8 text-center text-red-500 bg-red-50 rounded-lg border border-red-100">
            <AlertOctagon className="h-8 w-8 mx-auto mb-2 text-red-400" />
            <p className="font-semibold">Unable to load water stress data.</p>
         </div>
      );
  }

  // Process data for chart: Calculate ETc = ET0 * Kc
  const chartData = data.records.map((r: any) => ({
    ...r,
    etc: Number((r.et0 * kc).toFixed(2)), // Crop Evapotranspiration
    deficit: Number((r.precip - (r.et0 * kc)).toFixed(2)) // Daily Balance
  }));

  // Calculate current stress (accumulated deficit over last 7 days)
  const todayIndex = chartData.findIndex((r: any) => r.type === "forecast");
  const recentData = todayIndex > 7 ? chartData.slice(todayIndex - 7, todayIndex) : chartData.slice(0, 7);
  const weeklyDeficit = recentData.reduce((acc: number, cur: any) => acc + (cur.precip - cur.etc), 0);
  
  const stressLevel = weeklyDeficit < -20 ? "High" : weeklyDeficit < -10 ? "Moderate" : "Low";
  const stressColor = stressLevel === "High" ? "text-red-600" : stressLevel === "Moderate" ? "text-orange-500" : "text-green-600";

  return (
    <div className="card fade-in space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
           <h3 className="text-lg font-semibold flex items-center gap-2 dark:text-slate-200">
             <Droplets className="h-5 w-5 text-blue-500" /> 
             Water Stress Analysis
           </h3>
           <p className="text-sm text-muted-foreground dark:text-slate-400">FAO-56 Penman-Monteith (ET₀ vs Precipitation)</p>
        </div>

        {/* Crop Coefficient Selector */}
        <div className="flex items-center gap-2 bg-gray-50 dark:bg-slate-800/50 p-2 rounded-lg border border-transparent dark:border-slate-700">
           <span className="text-xs font-medium text-gray-500 dark:text-slate-400">Crop Stage (Kc):</span>
           <select 
             className="text-sm border-none bg-transparent font-medium focus:ring-0 cursor-pointer dark:text-slate-200"
             value={kc}
             onChange={(e) => setKc(Number(e.target.value))}
           >
             <option value={0.4} className="dark:bg-slate-800">Initial (0.4)</option>
             <option value={0.7} className="dark:bg-slate-800">Development (0.7)</option>
             <option value={1.0} className="dark:bg-slate-800">Mid-Season (1.0)</option>
             <option value={0.8} className="dark:bg-slate-800">Late Season (0.8)</option>
             <option value={1.2} className="dark:bg-slate-800">Stress/High (1.2)</option>
           </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Section */}
        <div className="lg:col-span-2 h-[350px]">
           <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                   <linearGradient id="colorPrecip" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1}/>
                   </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.2} stroke="#94a3b8" />
                <XAxis 
                   dataKey="date" 
                   tick={{fontSize: 10, fill: '#94a3b8'}} 
                   tickFormatter={(val) => val.slice(5)} // Show MM-DD
                   interval={4}
                   stroke="#475569"
                />
                <YAxis yAxisId="left" tick={{fontSize: 10, fill: '#94a3b8'}} label={{ value: 'mm', angle: -90, position: 'insideLeft', fill: '#94a3b8' }} stroke="#475569" />
                <Tooltip 
                   contentStyle={{ borderRadius: '8px', border: '1px solid #334155', background: '#1e293b', color: '#f8fafc' }}
                   labelFormatter={(label) => new Date(label).toDateString()}
                />
                <Legend iconType="circle" wrapperStyle={{ color: '#94a3b8' }} />
                
                {/* Precipitation Bar */}
                <Bar yAxisId="left" dataKey="precip" name="Precipitation" fill="url(#colorPrecip)" barSize={10} radius={[2, 2, 0, 0]} />
                
                {/* ET0 Reference Line */}
                <Line yAxisId="left" type="monotone" dataKey="et0" name="Ref. ET (ET₀)" stroke="#fb923c" dot={false} strokeWidth={2} strokeDasharray="5 5" />
                
                {/* Actual ET Area */}
                <Area yAxisId="left" type="monotone" dataKey="etc" name="Crop ET (ETc)" fill="#86efac" stroke="#22c55e" fillOpacity={0.3} />
                
              </ComposedChart>
           </ResponsiveContainer>
        </div>

        {/* Stats Section */}
        <div className="space-y-4">
           
           {/* Current Stress Indicator */}
           <div className={`p-4 rounded-lg border-l-4 
             ${stressLevel === "High" ? "border-red-500 bg-red-50 dark:bg-red-900/20" : stressLevel === "Moderate" ? "border-orange-500 bg-orange-50 dark:bg-orange-900/20" : "border-green-500 bg-green-50 dark:bg-green-900/20"}`}>
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Weekly Water Balance</h4>
              <div className={`text-3xl font-bold ${stressColor} dark:opacity-90`}>
                 {weeklyDeficit > 0 ? "+" : ""}{weeklyDeficit.toFixed(1)} mm
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                 {stressLevel === "High" ? "⚠️ Severe Deficit" : stressLevel === "Moderate" ? "⚠️ Mild Deficit" : "✅ Good Balance"}
              </p>
           </div>

           {/* Generic Stats */}
           <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-gray-50 dark:bg-slate-800/50 rounded-lg">
                 <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                    <Sun className="h-3 w-3" /> Total ETc
                 </div>
                 <div className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                    {(data.summary.total_et0_mm * kc).toFixed(1)} mm
                 </div>
              </div>
              
              <div className="p-3 bg-gray-50 dark:bg-slate-800/50 rounded-lg">
                 <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                    <Droplets className="h-3 w-3" /> Total Rain
                 </div>
                 <div className="text-lg font-semibold text-blue-600 dark:text-blue-400">
                    {data.summary.total_precip_mm} mm
                 </div>
              </div>
           </div>

           <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-xs text-blue-800 dark:text-blue-300">
              <p className="font-semibold mb-1">💡 Agronomist Tip:</p>
              {weeklyDeficit < -15 
                ? "Consider irrigation immediately. Crop demand significantly exceeds rainfall."
                : weeklyDeficit < 0 
                  ? "Monitor soil moisture. Mild deficit detected."
                  : "Water balance is positive. No immediate irrigation needed."
              }
           </div>
        </div>
      </div>
    </div>
  );
}
