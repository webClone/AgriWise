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
      {/* Unified floating topbar — same style for all views */}
      <div className={`${isMapView ? 'absolute top-0 left-0 right-0 z-30 pointer-events-none' : 'sticky top-0 z-30 pointer-events-none'}`}>
        <div className="px-4 pointer-events-auto flex justify-center">
          {topBarMap}
        </div>
      </div>

      <main className={`w-full ${isMapView ? 'flex-1 overflow-hidden' : 'flex-1 pt-2'}`}>
           {children}
      </main>
    </div>
  );
}
