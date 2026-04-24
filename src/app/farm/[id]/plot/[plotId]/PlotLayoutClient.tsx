"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import React from "react";

export default function PlotLayoutClient({
  children,
  topBarFull,
  topBarMap,
  farmId,
}: {
  children: React.ReactNode;
  topBarFull: React.ReactNode;
  topBarMap: React.ReactNode;
  farmId: string;
}) {
  const pathname = usePathname();
  
  const segments = pathname?.split('/') || [];
  const lastSegment = segments[segments.length - 1];
  const isMapView = lastSegment !== "user-inputs" && lastSegment !== "analysis" && lastSegment !== "raw-data" && lastSegment !== "live-assistance";

  return (
    <div className={`flex flex-col w-full ${isMapView ? 'h-screen' : 'min-h-screen'} plot-immersive`}>
      {isMapView ? (
        <>
          <div className="absolute top-0 left-0 right-0 z-30 pointer-events-none">
            <div className="px-4 pointer-events-auto flex justify-center">
              {topBarMap}
            </div>
          </div>
        </>
      ) : (
        <div className="px-3 md:px-5 py-2">
          <div className="flex flex-col md:flex-row items-stretch gap-3 mb-2">
            <Link 
                href={`/farm/${farmId}`} 
                className="flex items-center justify-center w-10 h-auto rounded-lg bg-slate-800/30 hover:bg-slate-700/40 border border-slate-700/30 transition-colors"
            >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5 text-slate-400">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                </svg>
            </Link>
            {topBarFull}
          </div>
        </div>
      )}

      <main className={`w-full ${isMapView ? 'flex-1 overflow-hidden' : 'flex-1'}`}>
           {children}
      </main>
    </div>
  );
}
