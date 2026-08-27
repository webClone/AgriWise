"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, Cpu, ShieldCheck } from "lucide-react";
import HeroSpatialPoster from "@/components/experience/SpatialStage/HeroSpatialPoster";

/* ═══ AgriWise R2 Pass 3B — HomeHero ═════════════════════════════
   Asymmetrical 65/35 Spatial Hero (Server HTML Component).
   Contains data-r2-chapter="hero" attribute for SpatialEngine discovery.
   
   4-Second Proposition Clarity:
   1. Category Statement: Agricultural intelligence, from every field to the entire food system.
   2. Subhead: Satellite, weather, soil, sensors and field evidence become traceable intelligence...
   3. Dual CTAs: Analyze My Field (Farmer) & AgriWise for Organizations (Enterprise/Gov).
   4. Trust Badge: Traceable evidence · uncertainty visible · powered by AgriBrain.
   ═══════════════════════════════════════════════════════════════ */

export default function HomeHero() {
  return (
    <section id="hero" data-r2-chapter="hero" className="r2-hero-section" data-r2-narrative="true" style={{ position: "relative", minHeight: "92vh", display: "flex", alignItems: "center" }}>
      {/* Static 0ms First-Paint Fallback Poster */}
      <HeroSpatialPoster />

      {/* Copy Protection Gradient Mask (Left Safe Zone) */}
      <div
        className="r2-hero-copy-protection"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "55%",
          height: "100%",
          zIndex: 5,
          background: "linear-gradient(90deg, #050a14 0%, #050a14 70%, rgba(5, 10, 20, 0.9) 85%, transparent 100%)",
          pointerEvents: "none",
        }}
      />

      <div className="marketing-container" style={{ position: "relative", zIndex: 10, width: "100%" }}>
        <div style={{ maxWidth: "580px" }}>
          {/* Section Badge */}
          <div
            className="marketing-section-badge"
            style={{
              background: "rgba(74, 222, 128, 0.08)",
              border: "1px solid rgba(74, 222, 128, 0.2)",
              color: "var(--field-green)",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "16px",
            }}
          >
            <Cpu size={12} /> Governed Agricultural Intelligence Platform
          </div>

          {/* High-Contrast Editorial Category Statement */}
          <h1
            style={{
              fontSize: "clamp(2.4rem, 4.8vw, 4.1rem)",
              fontWeight: 200,
              lineHeight: 1.08,
              letterSpacing: "-0.03em",
              color: "var(--text-primary)",
              margin: "0 0 20px",
            }}
          >
            Agricultural intelligence,{" "}
            <strong className="marketing-gradient-text" style={{ fontWeight: 800 }}>
              from every field to the entire food system.
            </strong>
          </h1>

          {/* Concrete Explanation Subhead */}
          <p
            style={{
              fontSize: "clamp(15px, 1.6vw, 18px)",
              color: "var(--text-muted)",
              lineHeight: 1.65,
              margin: "0 0 32px",
            }}
          >
            Satellite, weather, soil, sensors and field evidence become traceable intelligence for{" "}
            <strong style={{ color: "#f8fafc" }}>farm operations</strong>,{" "}
            <strong style={{ color: "#f8fafc" }}>agricultural risk</strong> and{" "}
            <strong style={{ color: "#f8fafc" }}>national food security</strong>.
          </p>

          {/* Dual Behavioral CTAs */}
          <div style={{ display: "flex", gap: "14px", flexWrap: "wrap", alignItems: "center", marginBottom: "28px" }}>
            <Link
              href="/farm/new"
              className="marketing-cta-primary"
              onClick={() => {
                if (typeof window !== "undefined") {
                  import("@/components/experience/analytics/MarketingTelemetry").then((m) =>
                    m.emitMarketingEvent("hero_farmer_cta")
                  );
                }
              }}
            >
              Analyze My Field <ArrowRight size={16} />
            </Link>
            <Link
              href="#command-center"
              className="marketing-cta-secondary"
              onClick={() => {
                if (typeof window !== "undefined") {
                  import("@/components/experience/analytics/MarketingTelemetry").then((m) =>
                    m.emitMarketingEvent("hero_org_cta")
                  );
                }
              }}
            >
              AgriWise for Organizations
            </Link>
          </div>

          {/* Quiet Trust Badge */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#64748b" }}>
            <ShieldCheck size={14} color="#4ade80" /> Traceable evidence · uncertainty visible · powered by AgriBrain
          </div>
        </div>
      </div>
    </section>
  );
}
