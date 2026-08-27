"use client";

import React, { useEffect, useState, useRef } from "react";
import { selectPlot } from "../world/selectors";
import opticalMeta from "../world/demo-optical.meta.json";

/* ═══ AgriWise HeroSpatialPoster ═════════════════════════════════
   First-frame static visual fallback matching canonical PLOT-017
   and the master hero aerial photograph with 1:1 pixel registration.
   ═══════════════════════════════════════════════════════════════ */

export default function HeroSpatialPoster() {
  const [isReady, setIsReady] = useState(false);
  const [unmounted, setUnmounted] = useState(false);
  const [containerBox, setContainerBox] = useState<{ width: number; height: number; left: number; top: number }>({
    width: 0,
    height: 0,
    left: 0,
    top: 0,
  });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const updateBox = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const imgAR = (opticalMeta.width || 1376) / (opticalMeta.height || 768);
      const vpAR = w / h;

      let renderW: number;
      let renderH: number;
      let left: number;
      let top: number;

      if (vpAR > imgAR) {
        renderW = w;
        renderH = w / imgAR;
        left = 0;
        top = (h - renderH) / 2;
      } else {
        renderH = h;
        renderW = h * imgAR;
        left = (w - renderW) / 2;
        top = 0;
      }

      setContainerBox({ width: renderW, height: renderH, left, top });
    };

    updateBox();
    window.addEventListener("resize", updateBox);

    const handleWebGlReady = () => {
      setIsReady(true);
      setTimeout(() => setUnmounted(true), 350);
    };

    window.addEventListener("agriwise_webgl_ready", handleWebGlReady);

    return () => {
      window.removeEventListener("resize", updateBox);
      window.removeEventListener("agriwise_webgl_ready", handleWebGlReady);
    };
  }, []);

  if (unmounted) return null;

  const plot = selectPlot("PLOT-017");
  const coords = plot?.coordinates || [];
  const [minLng, minLat, maxLng, maxLat] = opticalMeta.bounds;

  const latToMercatorY = (latDeg: number) => {
    const latRad = (latDeg * Math.PI) / 180;
    return 0.5 - (0.5 / Math.PI) * Math.log(Math.tan(Math.PI / 4 + latRad / 2));
  };

  const yNorth = latToMercatorY(maxLat);
  const ySouth = latToMercatorY(minLat);

  return (
    <div
      ref={containerRef}
      className="r2-hero-spatial-poster"
      aria-hidden="true"
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        overflow: "hidden",
        zIndex: 2,
        opacity: isReady ? 0 : 1,
        transition: "opacity 250ms cubic-bezier(0.4, 0, 0.2, 1)",
      }}
    >
      {containerBox.width > 0 && (
        <div
          style={{
            position: "absolute",
            left: `${containerBox.left}px`,
            top: `${containerBox.top}px`,
            width: `${containerBox.width}px`,
            height: `${containerBox.height}px`,
          }}
        >
          {/* Master Hero Optical Aerial Photography */}
          <img
            src="/r2/hero-field-master.webp"
            alt=""
            style={{
              width: "100%",
              height: "100%",
              display: "block",
              filter: "brightness(0.95) contrast(1.05)",
            }}
          />

          {/* Master PLOT-017 Vector Overlay - locked 1:1 to raster pixels */}
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              pointerEvents: "none",
            }}
          >
            <polygon
              points={coords
                .map(([lng, lat]) => {
                  const x = ((lng - minLng) / (maxLng - minLng)) * 100;
                  const yMerc = latToMercatorY(lat);
                  const y = ((yMerc - yNorth) / (ySouth - yNorth)) * 100;
                  return `${x.toFixed(3)},${y.toFixed(3)}`;
                })
                .join(" ")}
              fill="rgba(74, 222, 128, 0.08)"
              stroke="#4ade80"
              strokeWidth="0.25"
            />
          </svg>
        </div>
      )}
    </div>
  );
}
