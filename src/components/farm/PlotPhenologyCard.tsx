"use client";

import { useEffect, useState } from "react";

interface PhenologyData {
  crop: string;
  current_stage: string;
  next_stage: string | null;
  gdd_total: number;
  gdd_to_next_stage: number | null;
  gdd_requirements: Record<string, number>;
  base_temp_c: number;
  period_days: number;
}

interface CropCalendar {
  cycle_days: number;
  base_temp: number;
  optimal_temp: { min: number; max: number };
  gdd_requirements: Record<string, number>;
}

interface CropKc {
  kc_initial: number;
  kc_mid: number;
  kc_late: number;
  current_kc?: number;
}

interface PlotPhenologyCardProps {
  lat: number;
  lng: number;
  crop: string;
}

const STAGE_ICONS: Record<string, string> = {
  "pre-emergence": "🌱",
  "emergence": "🌿",
  "vegetative": "🌾",
  "v6": "🌽",
  "tillering": "🌾",
  "flowering": "🌸",
  "tasseling": "🌽",
  "heading": "🌾",
  "fruit_set": "🍅",
  "pod_fill": "🫘",
  "veraison": "🍇",
  "bulking": "🥔",
  "maturity": "✨",
  "harvest": "🎉",
  "ripening": "🍎",
  "unknown": "❓"
};

const STAGE_NAMES_AR: Record<string, string> = {
  "pre-emergence": "قبل الإنبات",
  "emergence": "الإنبات",
  "vegetative": "النمو الخضري",
  "v6": "المرحلة V6",
  "tillering": "التفريع",
  "flowering": "الإزهار",
  "tasseling": "التزهير",
  "heading": "الإسبال",
  "fruit_set": "عقد الثمار",
  "pod_fill": "امتلاء القرون",
  "veraison": "التلوين",
  "bulking": "تضخم الدرنات",
  "maturity": "النضج",
  "harvest": "الحصاد",
  "ripening": "النضوج",
  "bud_break": "تفتح البراعم",
  "tuber_initiation": "بدء الدرنات",
  "unknown": "غير محدد"
};

export default function PlotPhenologyCard({ lat, lng, crop }: PlotPhenologyCardProps) {
  const [phenology, setPhenology] = useState<PhenologyData | null>(null);
  const [calendar, setCalendar] = useState<CropCalendar | null>(null);
  const [kc, setKc] = useState<CropKc | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);

        // Fetch GDD accumulation
        // Fetch GDD accumulation via Proxy
        const gddRes = await fetch(`/api/proxy?path=/phenology/gdd&lat=${lat}&lng=${lng}&crop=${crop}&days=90`);
        const gddData = await gddRes.json();
        
        if (!gddData.error) {
          setPhenology(gddData);
        }

        // Fetch crop calendar
        // Fetch crop calendar via Proxy
        const calRes = await fetch(`/api/proxy?path=/phenology/calendar&crop=${crop}`);
        const calData = await calRes.json();
        
        if (!calData.error) {
          setCalendar(calData);
        }

        // Fetch Kc coefficients
        // Fetch Kc coefficients via Proxy
        const kcRes = await fetch(`/api/proxy?path=/phenology/kc&crop=${crop}&growth_stage=${gddData?.current_stage || ''}`);
        const kcData = await kcRes.json();
        
        if (!kcData.error) {
          setKc(kcData);
        }

      } catch (err) {
        console.error("Phenology fetch error:", err);
      } finally {
        setLoading(false);
      }
    }

    if (lat && lng && crop) {
      fetchData();
    }
  }, [lat, lng, crop]);

  if (loading) {
    return (
      <div className="card h-64 animate-pulse bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-6">
        <div className="h-6 bg-slate-200 dark:bg-slate-700 rounded w-1/3 mb-4"></div>
        <div className="h-24 bg-slate-200 dark:bg-slate-700 rounded"></div>
      </div>
    );
  }

  // Calculate progress percentage
  const stages = phenology?.gdd_requirements ? Object.entries(phenology.gdd_requirements) : [];
  const maxGDD = stages.length > 0 ? Math.max(...stages.map(([, v]) => v)) : 1000;
  const progressPercent = phenology ? Math.min(100, (phenology.gdd_total / maxGDD) * 100) : 0;

  return (
    <div className="card fade-in p-6 border border-slate-200 dark:border-slate-700 bg-gradient-to-br from-teal-50 to-slate-50 dark:from-teal-950 dark:to-slate-900 text-slate-900 dark:text-white">
      <h3 className="m-0 mb-4 font-semibold flex items-center gap-2 text-lg">
        <span>📈</span> مراحل النمو (GDD)
      </h3>

      {phenology ? (
        <>
          {/* Current Stage */}
          <div className="flex items-center gap-4 mb-6 p-4 rounded-xl border border-teal-100 dark:border-teal-900/30 bg-white/50 dark:bg-white/5">
            <div className="text-5xl">
              {STAGE_ICONS[phenology.current_stage] || "🌱"}
            </div>
            <div className="flex-1">
              <div className="text-[0.65rem] text-slate-500 dark:text-slate-400 uppercase tracking-widest font-bold">
                المرحلة الحالية
              </div>
              <div className="text-xl font-bold text-slate-800 dark:text-slate-100">
                {STAGE_NAMES_AR[phenology.current_stage] || phenology.current_stage}
              </div>
              {phenology.next_stage && (
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  التالي: {STAGE_NAMES_AR[phenology.next_stage] || phenology.next_stage}
                  {phenology.gdd_to_next_stage && (
                    <span className="text-teal-600 dark:text-teal-400 font-semibold"> ({phenology.gdd_to_next_stage.toFixed(0)} GDD)</span>
                  )}
                </div>
              )}
            </div>
            <div className="text-left">
              <div className="text-3xl font-bold text-teal-600 dark:text-teal-400 leading-none">
                {phenology.gdd_total.toFixed(0)}
              </div>
              <div className="text-[0.65rem] text-slate-500 dark:text-slate-500 mt-1">
                وحدة حرارية (GDD)
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mb-4">
            <div className="h-6 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden relative border border-slate-300 dark:border-slate-700">
              <div 
                style={{ width: `${progressPercent}%` }}
                className="h-full bg-gradient-to-r from-teal-500 to-cyan-500 transition-all duration-500 ease-out rounded-full"
              ></div>
              
              {/* Stage markers */}
              {stages.map(([stage, gdd], i) => (
                <div 
                  key={i}
                  className={`absolute top-0 bottom-0 w-0.5 ${phenology.gdd_total >= gdd ? "bg-white/40" : "bg-slate-900/10 dark:bg-white/10"}`}
                  style={{ left: `${(gdd / maxGDD) * 100}%` }}
                  title={`${STAGE_NAMES_AR[stage] || stage}: ${gdd} GDD`}
                />
              ))}
            </div>
            
            {/* Stage labels */}
            <div className="flex justify-between mt-2 text-[0.6rem] text-slate-500 dark:text-slate-400 font-medium">
              {stages.slice(0, 4).map(([stage], i) => (
                <span key={i}>{STAGE_ICONS[stage] || "•"} {STAGE_NAMES_AR[stage] || stage}</span>
              ))}
            </div>
          </div>

          {/* Kc and Info Row */}
          <div className="grid grid-cols-3 gap-2">
            <div className="p-3 bg-white/60 dark:bg-white/5 rounded-lg text-center border border-slate-100 dark:border-transparent">
              <div className="text-[0.6rem] text-slate-500 dark:text-slate-400 mb-1">معامل Kc</div>
              <div className="text-lg font-bold text-blue-600 dark:text-blue-400">
                {kc?.current_kc?.toFixed(2) || kc?.kc_mid?.toFixed(2) || "N/A"}
              </div>
            </div>
            <div className="p-3 bg-white/60 dark:bg-white/5 rounded-lg text-center border border-slate-100 dark:border-transparent">
              <div className="text-[0.6rem] text-slate-500 dark:text-slate-400 mb-1">الحرارة الأساسية</div>
              <div className="text-lg font-bold text-amber-500 dark:text-amber-400">
                {phenology.base_temp_c}°C
              </div>
            </div>
            <div className="p-3 bg-white/60 dark:bg-white/5 rounded-lg text-center border border-slate-100 dark:border-transparent">
              <div className="text-[0.6rem] text-slate-500 dark:text-slate-400 mb-1">دورة المحصول</div>
              <div className="text-lg font-bold text-purple-600 dark:text-purple-400">
                {calendar?.cycle_days || "?"} يوم
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center p-8 text-slate-500 dark:text-slate-400">
          <div className="text-4xl mb-2 opacity-50">📈</div>
          <p>لا تتوفر بيانات النمو لهذا المحصول</p>
          <p className="text-xs opacity-70">تأكد من تحديد المحصول ({crop})</p>
        </div>
      )}
    </div>
  );
}
