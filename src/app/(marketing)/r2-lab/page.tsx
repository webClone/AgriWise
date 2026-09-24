"use client";

import React from "react";
import SpatialEngine from "@/components/experience/SpatialStage/SpatialEngine";
import HomeHero from "@/components/marketing/home/HomeHero";
import ScaleSovereignCarousel from "@/components/marketing/home/ScaleSovereignCarousel";
import "@/components/marketing/marketing.css";

/* ═══ AgriWise R2 — Vertical Slice Prototype (/r2-lab) ═════════
   Pass 3B Spatial Engine Verification Sandbox.
   ═══════════════════════════════════════════════════════════════ */

export default function R2LabPage() {
  return (
    <div style={{ position: "relative", minHeight: "100vh" }}>
      <SpatialEngine />
      <main style={{ position: "relative", zIndex: 10 }}>
        <HomeHero />
        <ScaleSovereignCarousel />
      </main>
    </div>
  );
}
