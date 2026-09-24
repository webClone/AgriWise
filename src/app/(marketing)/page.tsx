import React from "react";
import HomeNav from "@/components/marketing/HomeNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import { Reveal } from "@/components/marketing/motion/Reveal";

// ═══ The AgriBrain Category Narrative: High-Density Interactive Carousels ═══
// Compressed from 11 tall vertical stacks into 4 dynamic experiential carousels
import HomeHero from "@/components/marketing/home/HomeHero";
import PerceptionMemoryCarousel from "@/components/marketing/home/PerceptionMemoryCarousel";
import ReasoningSimulationCarousel from "@/components/marketing/home/ReasoningSimulationCarousel";
import ScaleSovereignCarousel from "@/components/marketing/home/ScaleSovereignCarousel";
import ArchitectureLearningCarousel from "@/components/marketing/home/ArchitectureLearningCarousel";
import StakeholderPlatformsSection from "@/components/marketing/home/StakeholderPlatformsSection";
import FinalCTA from "@/components/marketing/home/FinalCTA";

import "@/components/marketing/marketing.css";

/* ═══ AgriWise: The Intelligence Layer for Agricultural Reality ═══
   Deep-Tech Cognitive Narrative Architecture (MESIA R2 Monograph)
   
   00. Hero & Operational Reality Console
   01. Module 01: Perception & Memory (Cognitive Loop · PlotWorldline · Multi-Modal Reconstruction)
   02. Module 02: Reasoning & Simulation (Causal Pearl DAG · 72h Vadose Counterfactuals)
   03. Module 03: Scale & Sovereignty (Fractal Scale Microzone-to-Basin · Sovereign Balance Sheet)
   04. Module 04: Architecture & Compounding Moat (7 Machine Layers & DAG · Continuous Learning & Omega)
   05. Stakeholder Platforms (4 Product Doors: Farmers, Enterprises, Cooperatives, Sovereigns)
   06. Deployment Gateways & Strategic Call to Action
   ═════════════════════════════════════════════════════════════════════════════════════════ */

export default function Home() {
  return (
    <div className="marketing-root" style={{ position: "relative", minHeight: "100vh", background: "#05070B" }}>
      {/* 1. Top Navigation */}
      <HomeNav />

      {/* 2. Consolidated High-Density Experiential Narrative */}
      <main style={{ position: "relative", zIndex: 10 }}>
        {/* 00. Hero & Live Operational Reality Console */}
        <HomeHero />

        {/* 01. Module 01: Perception & Memory (Loop · Worldline · Reconstruction Slider) */}
        <Reveal direction="up" distance={32} threshold={0.06}>
          <PerceptionMemoryCarousel />
        </Reveal>

        {/* 02. Module 02: Reasoning & Simulation (Causal Inference · Counterfactual Curves) */}
        <Reveal direction="up" distance={32} threshold={0.06}>
          <ReasoningSimulationCarousel />
        </Reveal>

        {/* 03. Module 03: Scale & Sovereignty (Fractal Scale · Sovereign Governance) */}
        <Reveal direction="up" distance={32} threshold={0.06}>
          <ScaleSovereignCarousel />
        </Reveal>

        {/* 04. Module 04: Architecture & Compounding Moat (7 Layers & DAG · Continuous Learning) */}
        <Reveal direction="up" distance={32} threshold={0.06}>
          <ArchitectureLearningCarousel />
        </Reveal>

        {/* 05. Deployment Platforms (4 Stakeholder Doors) */}
        <Reveal direction="up" distance={32} threshold={0.06}>
          <StakeholderPlatformsSection />
        </Reveal>

        {/* 06. Final Strategic Gateways & Deployment CTA */}
        <Reveal direction="up" distance={32} threshold={0.06}>
          <FinalCTA />
        </Reveal>
      </main>

      {/* 3. Marketing Footer */}
      <div style={{ position: "relative", zIndex: 10, background: "#05070B" }}>
        <MarketingFooter />
      </div>
    </div>
  );
}
