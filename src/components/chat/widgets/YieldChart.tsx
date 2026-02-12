import React from 'react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';
import { YieldPredictionProps } from './types';

export const YieldChart: React.FC<YieldPredictionProps> = ({ data }) => {
  const { predicted_yield_t_ha, crop } = data;
  
  // Generate a bell curve distribution based on the predicted yield
  // Mean = predicted_yield, StdDev = predicted_yield * 0.15 (assumed)
  const mean = predicted_yield_t_ha;
  const stdDev = mean * 0.15;
  
  const chartData = [];
  const minX = Math.max(0, mean - 3 * stdDev);
  const maxX = mean + 3 * stdDev;
  const step = (maxX - minX) / 20;

  for (let x = minX; x <= maxX; x += step) {
    const y = (1 / (stdDev * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((x - mean) / stdDev, 2));
    chartData.push({ yield: x, probability: y });
  }

  // Normalize probability for display
  const maxProb = Math.max(...chartData.map(d => d.probability));
  const displayData = chartData.map(d => ({ 
      ...d, 
      displayProb: (d.probability / maxProb) * 100 
  }));

  return (
    <div className="bg-white/90 p-3 rounded-lg border border-emerald-100 shadow-sm mt-2 max-w-sm">
      <div className="mb-2">
        <h4 className="text-sm font-semibold text-emerald-900 flex items-center gap-2">
           Predicted Yield ({crop})
        </h4>
        <div className="text-2xl font-bold text-emerald-600">
            {predicted_yield_t_ha.toFixed(1)} <span className="text-xs text-neutral-500 font-normal">t/ha</span>
        </div>
      </div>
      
      <div className="h-32 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={displayData}>
            <XAxis 
                dataKey="yield" 
                tickFormatter={(val) => val.toFixed(1)} 
                tick={{fontSize: 10}}
                interval={4}
            />
            <Tooltip 
                labelFormatter={(val) => `Yield: ${Number(val).toFixed(2)} t/ha`}
                formatter={(val: number) => [`${val.toFixed(0)}%`, 'Probability']}
            />
            <Area type="monotone" dataKey="displayProb" fill="#10b981" stroke="#059669" fillOpacity={0.2} />
            <ReferenceLine x={mean} stroke="red" strokeDasharray="3 3" label={{ position: 'top', value: 'Avg', fontSize: 10, fill: 'red' }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      
      {data.limiting_factors.length > 0 && (
          <div className="mt-2 pt-2 border-t border-emerald-50 text-xs">
              <span className="font-medium text-amber-600">Risk Factors:</span>
              <ul className="list-disc pl-4 text-neutral-600 mt-1">
                  {data.limiting_factors.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
          </div>
      )}
    </div>
  );
};
