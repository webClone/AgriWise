"use client";

import React from 'react';

interface Stage {
  stage: string;
  nameAr: string;
  startDay?: number;
  endDay?: number;
  tasks?: string[];
}

interface CropTimelineProps {
  stages: Stage[];
  currentStage?: string;
}

export default function CropTimeline({ stages, currentStage }: CropTimelineProps) {
  // Find index of current stage
  const currentIndex = stages.findIndex(s => s.stage === currentStage);
  const activeIndex = currentIndex === -1 ? 0 : currentIndex;

  return (
    <div className="w-full">
      {/* Container fits parent width, no forced scroll unless extremely small */}
      <div className="w-full px-2">
        <div className="relative w-full">
          
          {/* Progress Bar Background */}
          <div className="absolute top-1/2 right-0 w-full h-1.5 bg-slate-700 -translate-y-1/2 rounded-full" />
          
          {/* Active Progress Line */}
          <div 
            className="absolute top-1/2 right-0 h-1.5 bg-gradient-to-r from-green-600 to-green-400 -translate-y-1/2 rounded-full transition-all duration-700 ease-out"
            style={{ width: `${(activeIndex / (stages.length - 1)) * 100}%` }}
          />

          <div className="relative flex justify-between w-full">
            {stages.map((stage, index) => {
              const isCompleted = index <= activeIndex;
              const isCurrent = index === activeIndex;

              return (
                <div key={stage.stage} className="flex flex-col items-center group relative cursor-pointer pt-2 px-1">
                  {/* Stage Node */}
                  <div 
                    className={`
                      w-10 h-10 rounded-full flex items-center justify-center z-10 
                      border-4 transition-all duration-300 shadow-md relative bg-slate-800
                      ${isCompleted 
                        ? 'border-green-500 text-white shadow-green-500/30 !bg-green-500' // Added !bg-green-500 to force fill
                        : 'border-slate-600 text-slate-400'}
                      ${isCurrent ? 'scale-110 border-white ring-4 ring-green-500/30' : ''}
                    `}
                  >
                    {isCompleted ? (
                      <svg className="w-5 h-5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <span className="text-sm font-bold">{index + 1}</span>
                    )}
                  </div>

                  {/* Stage Name */}
                  <div className={`mt-3 text-xs sm:text-sm font-bold text-center transition-colors duration-300 max-w-[80px] leading-tight ${
                    isCurrent ? 'text-green-400' : isCompleted ? 'text-slate-300' : 'text-slate-500'
                  }`}>
                    {stage.nameAr}
                  </div>

                  {/* Hover Details (Dark Tooltip) */}
                  <div className="absolute bottom-full mb-3 w-40 bg-slate-800 shadow-xl rounded-xl p-3 hidden group-hover:block z-20 border border-slate-700 opacity-0 group-hover:opacity-100 transition-opacity transform translate-y-2 group-hover:translate-y-0 left-1/2 -translate-x-1/2 pointer-events-none">
                    <h4 className="font-bold text-white mb-1 text-center border-b border-slate-700 pb-1 text-xs">{stage.nameAr}</h4>
                    {stage.tasks && stage.tasks.length > 0 ? (
                      <ul className="text-[10px] text-slate-300 list-disc list-inside space-y-1 mt-1">
                        {stage.tasks.slice(0, 3).map((task, i) => (
                          <li key={i} className="truncate">{task}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[10px] text-slate-500 text-center">لا توجد تفاصيل</p>
                    )}
                    {/* Tooltip Arrow */}
                    <div className="absolute bottom-[-5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-slate-800 rotate-45 border-r border-b border-slate-700"></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
