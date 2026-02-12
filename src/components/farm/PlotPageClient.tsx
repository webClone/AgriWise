"use client";

import { useState } from "react";
import StartCycleModal from "@/components/farm/StartCycleModal";
import CycleDashboard from "@/components/farm/CycleDashboard";
import RecalculateButton from "@/components/farm/RecalculateButton";

interface PlotPageClientProps {
  plotId: string;
  activeCycle: any | null;
  tasks: any[];
}

export default function PlotPageClient({ plotId, activeCycle, tasks }: PlotPageClientProps) {
  const [showStartModal, setShowStartModal] = useState(false);

  return (
    <>
      <div className="mb-6 fade-in">
        <div className="flex justify-between items-center mb-4">
          <h3 className="m-0 font-semibold text-slate-900 dark:text-white">🌾 الدورة الزراعية الحالية</h3>
          {activeCycle ? (
            <RecalculateButton cycleId={activeCycle.id} />
          ) : (
            <button 
                onClick={() => setShowStartModal(true)}
                className="btn btn-primary px-4 py-2 text-sm"
            >
                + بدء دورة جديدة
            </button>
          )}
        </div>

        {!activeCycle ? (
            <div className="text-center p-8 text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 rounded-lg mt-4 border border-slate-200 dark:border-slate-700">
                <div className="text-4xl mb-2">🌱</div>
                <p>لا توجد زراعة حالية في هذه القطعة.</p>
                <button 
                    onClick={() => setShowStartModal(true)}
                    className="text-primary-600 dark:text-primary-400 underline font-medium mt-2 bg-transparent border-none cursor-pointer"
                >
                    اضغط هنا لبدء دورة زراعية
                </button>
            </div>
        ) : (
            <CycleDashboard cycle={activeCycle} tasks={tasks} />
        )}
      </div>

      {showStartModal && (
        <StartCycleModal 
            plotId={plotId} 
            onClose={() => setShowStartModal(false)} 
        />
      )}
    </>
  );
}
