"use client";

import { Camera, AlertTriangle } from "lucide-react";
import PlotPhotoGallery from "./PlotPhotoGallery";
import IPCameraManager from "./IPCameraManager";

interface PlotPhoto {
  id: string;
  url: string;
  type: string;
  date: string | Date;
  [key: string]: any;
}

interface PlotVisualGroundTruthProps {
  plot: {
      id: string;
      photos?: PlotPhoto[];
      cameras?: any[];
      [key: string]: any;
  };
}

export default function PlotVisualGroundTruth({ plot }: PlotVisualGroundTruthProps) {
  const photos = plot.photos || [];
  const sortedPhotos = [...photos].sort((a: PlotPhoto, b: PlotPhoto) => new Date(b.date).getTime() - new Date(a.date).getTime());
  const lastPhoto = sortedPhotos[0];
  
  let daysSince = 0;
  let showMotivationalWarning = false;

  if (lastPhoto) {
      const diffTime = Math.abs(new Date().getTime() - new Date(lastPhoto.date).getTime());
      daysSince = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      if (daysSince > 10) showMotivationalWarning = true;
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      
      {/* Header */}
      <div className="bg-slate-50 dark:bg-slate-950 px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-start">
        <div>
            <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <Camera className="text-blue-500" size={18} />
            Visual Ground Truth
            </h3>
            <p className="text-[10px] text-slate-500 mt-1">
                Improves satellite anomaly validation & yield verification.
            </p>
        </div>
        
        {showMotivationalWarning && (
            <div className="flex items-center gap-2 bg-amber-50 dark:bg-amber-900/20 px-3 py-1.5 rounded-lg border border-amber-100 dark:border-amber-800/50">
                <AlertTriangle size={14} className="text-amber-500" />
                <div className="flex flex-col">
                    <p className="text-[10px] font-bold text-amber-600 dark:text-amber-400 leading-tight">
                        Last photo: {daysSince} days ago
                    </p>
                    <p className="text-[9px] text-amber-600/80 dark:text-amber-500 leading-tight">
                        Add new to improve disease detection
                    </p>
                </div>
            </div>
        )}
      </div>

      <div className="p-6 space-y-8">
        
        {/* Photos Section */}
        <section>
            <PlotPhotoGallery plotId={plot.id} photos={plot.photos || []} />
        </section>

        <hr className="border-slate-100 dark:border-slate-800" />

        {/* Cameras Section */}
        <section>
            <IPCameraManager plotId={plot.id} cameras={plot.cameras || []} />
        </section>

      </div>
    </div>
  );
}
