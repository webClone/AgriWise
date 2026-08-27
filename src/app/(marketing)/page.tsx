import React from "react";
import HomeNav from "@/components/marketing/HomeNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import SpatialEngineWrapper from "@/components/experience/SpatialStage/SpatialEngineWrapper";
import HomeHero from "@/components/marketing/home/HomeHero";
import ScaleChapter from "@/components/marketing/home/ScaleChapter";
import EvidenceChapter from "@/components/marketing/home/EvidenceChapter";
import SpatialAgriBrainChapter from "@/components/marketing/home/SpatialAgriBrainChapter";
import SpatialAsmaeChapter from "@/components/marketing/home/SpatialAsmaeChapter";
import SpatialWorldlineChapter from "@/components/marketing/home/SpatialWorldlineChapter";
import StakeholderCommandCenter from "@/components/marketing/home/StakeholderCommandCenter";
import SpatialInstitutionalChapter from "@/components/marketing/home/SpatialInstitutionalChapter";
import SpatialSovereignChapter from "@/components/marketing/home/SpatialSovereignChapter";
import SpatialInfrastructureChapter from "@/components/marketing/home/SpatialInfrastructureChapter";
import FinalCTA from "@/components/marketing/home/FinalCTA";
import "@/components/marketing/marketing.css";

/* ═══ AgriWise R2 Pass 3 — Server Page Component ═══════════════
   Public marketing homepage rendered as a pure Server Component.
   
   Architecture:
   - Server HTML narrative structure with [data-r2-chapter] attributes
   - Client WebGL SpatialEngine island wrapper
   - Complete SEO and screen reader accessibility mirror
   ═══════════════════════════════════════════════════════════════ */

export default function Home() {
  return (
    <div style={{ position: "relative", minHeight: "100vh" }}>
      {/* 1. Persistent WebGL Canvas & HUD Client Island */}
      <SpatialEngineWrapper />

      {/* 2. Top Navigation */}
      <HomeNav />

      {/* 3. Accessible Server HTML Narrative Overlay */}
      <main style={{ position: "relative", zIndex: 10 }}>
        <HomeHero />
        <ScaleChapter />
        <EvidenceChapter />
        <SpatialAgriBrainChapter />
        <SpatialAsmaeChapter />
        <SpatialWorldlineChapter />
        <StakeholderCommandCenter />
        <SpatialInstitutionalChapter />
        <SpatialSovereignChapter />
        <SpatialInfrastructureChapter />
        <FinalCTA />
      </main>

      {/* 4. Footer */}
      <div style={{ position: "relative", zIndex: 10, background: "var(--surface-base)" }}>
        <MarketingFooter />
      </div>
    </div>
  );
}
