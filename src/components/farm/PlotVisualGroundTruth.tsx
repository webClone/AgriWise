"use client";

import { Camera } from "lucide-react";
import PlotPhotoGallery from "./PlotPhotoGallery";
import IPCameraManager from "./IPCameraManager";

interface PlotVisualGroundTruthProps {
  plot: any;
}

export default function PlotVisualGroundTruth({ plot }: PlotVisualGroundTruthProps) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      
      {/* Header */}
      <div className="bg-slate-50 dark:bg-slate-950 px-6 py-4 border-b border-slate-100 dark:border-slate-800">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
           <Camera className="text-blue-500" size={18} />
           Visual Ground Truth
        </h3>
        <p className="text-xs text-slate-500 mt-1">
            Manage on-ground imagery to validate satellite data.
        </p>
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
