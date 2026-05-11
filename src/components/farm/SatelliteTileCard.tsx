"use client";

/**
 * SatelliteTileCard — Shows the latest Sentinel-2 RGB satellite image
 * of the plot, fetched automatically by the tile runtime.
 *
 * Displayed in the Visual Ground Truth section alongside user-uploaded photos.
 * Auto-fetches a tile if none exists and lat/lng are provided.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Satellite, RefreshCw, Calendar, Eye, Sparkles, Download, Loader2 } from "lucide-react";

interface SatelliteTileCardProps {
  plotId: string;
  lat?: number;
  lng?: number;
  polygon?: any;
}

export default function SatelliteTileCard({ plotId, lat, lng, polygon }: SatelliteTileCardProps) {
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const autoFetchedRef = useRef(false);

  // Cache-bust the image URL when meta changes
  const imageUrl = `/api/agribrain/satellite-tile-image/${plotId}${meta?.fetched_at ? `?t=${meta.fetched_at}` : ""}`;

  const fetchMeta = useCallback(async () => {
    try {
      const res = await fetch(`/api/agribrain/satellite-tile-meta/${plotId}`);
      const data = await res.json();
      setMeta(data);
      setImageError(false);
      return data;
    } catch {
      setMeta(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, [plotId]);

  const triggerFetch = useCallback(async (force = false) => {
    setRefreshing(true);
    try {
      const parsedPolygon = typeof polygon === "string" ? JSON.parse(polygon) : polygon;

      // Step 1: Fetch the satellite tile
      const res = await fetch("/api/agribrain/satellite-tile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plot_id: plotId,
          lat: lat || 36.0,
          lng: lng || 3.0,
          polygon: parsedPolygon || null,
          force,
        }),
      });
      const result = await res.json();
      console.log("[SatelliteTile] Tile:", result.status);

      if (result.status === "fetched" || result.status === "cached") {
        // Step 2: Run LLM vision analysis on the tile
        let vision = null;
        try {
          const visionRes = await fetch("/api/agribrain/satellite-vision", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plot_id: plotId, lat: lat || 36.0, lng: lng || 3.0 }),
          });
          const visionData = await visionRes.json();
          if (visionData.status === "analyzed") {
            vision = visionData.vision;
            console.log("[SatelliteTile] Vision:", vision?.emergence_stage, `veg=${vision?.vegetation_pct}%`);
          } else {
            console.log("[SatelliteTile] Vision skipped:", visionData.status);
          }
        } catch (e) {
          console.warn("[SatelliteTile] Vision failed (non-blocking):", e);
        }

        // Step 3: Save image + LLM observation to DB together
        try {
          await fetch(`/api/agribrain/satellite-tile-save/${plotId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              fetched_date: result.metadata?.fetched_date || new Date().toISOString(),
              vision,  // LLM observation is embedded in the photo record
            }),
          });
          console.log("[SatelliteTile] Saved to DB with", vision ? "LLM observation" : "no vision");
        } catch (e) {
          console.warn("[SatelliteTile] DB save failed (non-blocking):", e);
        }
      }

      await fetchMeta();
    } catch (e) {
      console.warn("[SatelliteTile] Fetch failed:", e);
    } finally {
      setRefreshing(false);
    }
  }, [plotId, lat, lng, polygon, fetchMeta]);

  // On mount: check if tile exists, auto-fetch if not
  useEffect(() => {
    (async () => {
      const data = await fetchMeta();
      if (!data?.exists && !autoFetchedRef.current && lat && lng) {
        autoFetchedRef.current = true;
        console.log("[SatelliteTile] No tile cached, auto-fetching...");
        await triggerFetch(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plotId]);

  const tileDate = meta?.fetched_date
    ? new Date(meta.fetched_date as string).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  const dimensions = meta?.dimensions as number[] | undefined;
  const tileSizeKB = meta?.tile_size_bytes
    ? Math.round((meta.tile_size_bytes as number) / 1024)
    : null;

  // Loading state
  if (loading || (refreshing && !meta?.exists)) {
    return (
      <div className="rounded-xl border border-indigo-200 dark:border-indigo-800/50 bg-gradient-to-br from-indigo-50/80 to-blue-50/50 dark:from-indigo-950/30 dark:to-blue-950/20 p-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/50">
            <Satellite className="text-indigo-600 dark:text-indigo-400 animate-pulse" size={18} />
          </div>
          <div>
            <h4 className="font-semibold text-sm text-slate-800 dark:text-slate-200">
              Capturing Satellite View…
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mt-0.5">
              <Loader2 size={10} className="animate-spin" />
              Fetching Sentinel-2 imagery from Copernicus
            </p>
          </div>
        </div>
        <div className="mt-4 aspect-video rounded-lg bg-gradient-to-br from-slate-200 to-slate-100 dark:from-slate-800 dark:to-slate-900 animate-pulse" />
      </div>
    );
  }

  // No tile exists and couldn't auto-fetch
  if (!meta?.exists) {
    return (
      <div className="rounded-xl border border-dashed border-indigo-300 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/20 p-6">
        <div className="flex items-center gap-2 mb-2">
          <Satellite className="text-indigo-500" size={18} />
          <h4 className="font-semibold text-sm text-slate-800 dark:text-slate-200">
            Satellite View
          </h4>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          No satellite image captured yet. Click below to fetch the latest Sentinel-2 imagery for this plot.
        </p>
        <button
          onClick={() => triggerFetch(false)}
          disabled={refreshing}
          className="flex items-center gap-1.5 text-xs font-medium bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          {refreshing ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Satellite size={12} />
          )}
          {refreshing ? "Fetching from Sentinel-2..." : "Capture Satellite Image"}
        </button>
      </div>
    );
  }

  // Tile exists — show it
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-indigo-50 to-blue-50 dark:from-indigo-950/30 dark:to-blue-950/30 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-100 dark:bg-indigo-900/50">
            <Satellite className="text-indigo-600 dark:text-indigo-400" size={14} />
          </div>
          <div>
            <h4 className="font-semibold text-xs text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              Sentinel-2 RGB
              <span className="px-1.5 py-0.5 text-[9px] font-medium bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 rounded-full">
                Auto
              </span>
            </h4>
            {tileDate && (
              <p className="text-[10px] text-slate-500 dark:text-slate-400 flex items-center gap-1 mt-0.5">
                <Calendar size={9} />
                {tileDate}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => triggerFetch(true)}
            disabled={refreshing}
            className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 transition-colors disabled:opacity-50"
            title="Refresh satellite image"
          >
            <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors"
            title="Toggle full view"
          >
            <Eye size={13} />
          </button>
        </div>
      </div>

      {/* Image */}
      <div
        className={`relative cursor-pointer transition-all duration-300 ${
          expanded ? "aspect-auto" : "aspect-video"
        }`}
        onClick={() => setExpanded(!expanded)}
      >
        {!imageError ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={imageUrl}
            alt="Sentinel-2 satellite view of plot"
            className={`w-full object-cover transition-all duration-500 ${
              expanded ? "max-h-[600px] object-contain bg-black" : "h-full"
            }`}
            loading="lazy"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full aspect-video flex items-center justify-center bg-slate-100 dark:bg-slate-800">
            <p className="text-xs text-slate-500">Image loading failed</p>
          </div>
        )}

        {/* Overlay badge */}
        <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-1 rounded-md bg-black/60 backdrop-blur-sm">
          <Sparkles size={10} className="text-amber-400" />
          <span className="text-[9px] font-medium text-white/90">AgriBrain Vision</span>
        </div>

        {/* Dimensions badge */}
        {dimensions && (
          <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm">
            <span className="text-[9px] text-white/70">
              {dimensions[0]}×{dimensions[1]}px • {tileSizeKB}KB
            </span>
          </div>
        )}
      </div>

      {/* Footer info */}
      <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-950/50 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <p className="text-[10px] text-slate-500 dark:text-slate-400">
          Auto-captured from Sentinel-2 L2A • Updated weekly
        </p>
        <a
          href={imageUrl}
          download={`satellite_${plotId}.png`}
          className="p-1 rounded text-slate-400 hover:text-blue-600 transition-colors"
          title="Download satellite image"
          onClick={(e) => e.stopPropagation()}
        >
          <Download size={12} />
        </a>
      </div>
    </div>
  );
}
