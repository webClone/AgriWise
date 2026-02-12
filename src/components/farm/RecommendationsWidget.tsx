"use client";

import { useState, useEffect } from "react";

interface Recommendation {
  type: "soil" | "water" | "stage" | "pest";
  status: "success" | "warning" | "info" | "danger";
  message: string;
  tasks?: string[];
}

interface RecommendationsWidgetProps {
  cropCode: string;
  growthStage?: string;
  soilType?: string;
  region?: string;
}

export default function RecommendationsWidget({ cropCode, growthStage, soilType, region }: RecommendationsWidgetProps) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [cropInfo, setCropInfo] = useState<any>(null);

  useEffect(() => {
    if (cropCode) {
      fetchRecommendations();
    }
  }, [cropCode, growthStage]);

  const fetchRecommendations = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/farms/recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cropCode, growthStage, soilType, region }),
      });
      const data = await res.json();
      
      if (data.success) {
        setRecommendations(data.recommendations || []);
        setCropInfo(data.crop);
      }
    } catch (err) {
      console.error("Failed to fetch recommendations", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-4 bg-white dark:bg-slate-900 rounded-lg shadow-sm border border-slate-100 dark:border-slate-800 animate-pulse h-32"></div>;
  if (!recommendations.length && !cropInfo) return null;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg shadow-sm border border-gray-100 dark:border-slate-800 overflow-hidden">
      <div className="p-4 border-b border-gray-100 dark:border-slate-800 bg-gradient-to-r from-green-50 to-white dark:from-green-900/20 dark:to-slate-900 flex items-center justify-between">
        <h3 className="font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
          {cropInfo?.icon} نصائح ذكية لـ {cropInfo?.nameAr}
        </h3>
        <span className="text-xs text-green-600 dark:text-green-400 font-medium bg-green-100 dark:bg-green-900/30 px-2 py-1 rounded-full">
          محدث
        </span>
      </div>
      
      <div className="p-4 space-y-3">
        {recommendations.map((rec, idx) => (
          <div 
            key={idx}
            className={`
              p-3 rounded-lg border-l-4 text-sm
              ${rec.status === 'success' ? 'bg-green-50 dark:bg-green-900/10 border-green-500 text-green-800 dark:text-green-300' : ''}
              ${rec.status === 'warning' ? 'bg-yellow-50 dark:bg-yellow-900/10 border-yellow-500 text-yellow-800 dark:text-yellow-300' : ''}
              ${rec.status === 'info' ? 'bg-blue-50 dark:bg-blue-900/10 border-blue-500 text-blue-800 dark:text-blue-300' : ''}
              ${rec.status === 'danger' ? 'bg-red-50 dark:bg-red-900/10 border-red-500 text-red-800 dark:text-red-300' : ''}
            `}
          >
            <p className="font-medium">{rec.message}</p>
            {rec.tasks && rec.tasks.length > 0 && (
              <ul className="mt-2 space-y-1 ml-4 list-disc opacity-90">
                {rec.tasks.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            )}
          </div>
        ))}

        {!recommendations.length && (
          <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-2">لا توجد توصيات خاصة في الوقت الحالي.</p>
        )}
      </div>
    </div>
  );
}
