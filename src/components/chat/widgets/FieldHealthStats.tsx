import React from 'react';
import { CloudRain, Droplets, Sun, Thermometer } from 'lucide-react';
import { FieldIndicatorsProps } from './types';

export const FieldHealthStats: React.FC<FieldIndicatorsProps> = ({ data }) => {
  // Use the most recent data point (simulated "today" or future forecast)
  const latest = data[data.length - 1] || data[0]; 

  if (!latest) return null;

  return (
    <div className="bg-white/90 p-3 rounded-lg border border-blue-100 shadow-sm mt-2 max-w-sm">
      <h4 className="text-sm font-semibold text-blue-900 mb-3 flex items-center gap-2">
         Field Status ({latest.date})
      </h4>

      <div className="grid grid-cols-2 gap-2">
          {/* NDVI Card */}
          <div className="bg-green-50 p-2 rounded border border-green-100 flex flex-col items-center">
             <span className="text-xs text-green-600 font-medium">Vegetation (NDVI)</span>
             <span className="text-xl font-bold text-green-700">{latest.ndvi.toFixed(2)}</span>
          </div>

          {/* NDMI Card */}
          <div className="bg-cyan-50 p-2 rounded border border-cyan-100 flex flex-col items-center">
             <span className="text-xs text-cyan-600 font-medium">Moisture (NDMI)</span>
             <span className="text-xl font-bold text-cyan-700">{latest.ndmi.toFixed(2)}</span>
          </div>
      </div>
      
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-neutral-600">
          <div className="flex items-center gap-1.5">
             <Thermometer className="w-3.5 h-3.5 text-orange-500" />
             <span>{latest.temp_c}°C</span>
          </div>
          <div className="flex items-center gap-1.5">
             <CloudRain className="w-3.5 h-3.5 text-blue-500" />
             <span>{latest.rainfall_mm}mm Rain</span>
          </div>
      </div>
      
      <div className="mt-2 text-[10px] text-neutral-400 text-right">
          Source: {(latest as any).source || "Sentinel-2"}
      </div>
    </div>
  );
};
