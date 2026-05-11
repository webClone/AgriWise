"use client";

import { Camera, AlertTriangle } from "lucide-react";
import PlotPhotoGallery from "./PlotPhotoGallery";
import IPCameraManager from "./IPCameraManager";
import SatelliteTileCard from "./SatelliteTileCard";

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
  lat?: number;
  lng?: number;
  polygon?: any;
}

export default function PlotVisualGroundTruth({ plot, lat, lng, polygon }: PlotVisualGroundTruthProps) {
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
    <div className="rounded-2xl border border-white/[0.06] overflow-hidden" style={{ background: "linear-gradient(180deg, rgba(11,16,21,0.9) 0%, rgba(8,12,25,0.95) 100%)" }}>
      
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/[0.04] flex justify-between items-start">
        <div>
            <h3 className="font-semibold text-white flex items-center gap-2 text-sm">
            <Camera className="text-blue-500" size={18} />
            Visual Ground Truth
            </h3>
            <p className="text-[10px] text-slate-500 mt-1">
                Improves satellite anomaly validation & yield verification.
            </p>
        </div>
        
        {showMotivationalWarning && (
            <div className="flex items-center gap-2 bg-amber-500/10 px-3 py-1.5 rounded-lg border border-amber-500/15">
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
        
        {/* Satellite RGB Tile — Auto-captured from Sentinel-2 */}
        <section>
            <SatelliteTileCard plotId={plot.id} lat={lat} lng={lng} polygon={polygon} />
        </section>

        <hr className="border-white/[0.04]" />

        {/* User-Uploaded Photos */}
        <section>
            <PlotPhotoGallery plotId={plot.id} photos={plot.photos || []} />
        </section>

        <hr className="border-white/[0.04]" />

        {/* Cameras Section */}
        <section>
            <IPCameraManager plotId={plot.id} cameras={plot.cameras || []} />
        </section>

      </div>
    </div>
  );
}
