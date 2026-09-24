"use client";

import React, { useState, useRef, useEffect } from "react";
import Image from "next/image";
import {
  ArrowRight,
  Sparkles,
  Cpu,
  Play,
  Pause,
  Sun,
  Droplets,
  Wind,
  Send,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import type { Locale } from "@/lib/i18n/types";

/* ═══ 01. The Perception Breakthrough (Hero) ════════════════════
   Dribbble AI-Powered Farming Dashboard Standard (Musemind AgrixAI)
   (Reference: https://dribbble.com/shots/27375170-AI-Powered-Farming-Dashboard-Design)
   
   - High-contrast obsidian & emerald glassmorphism
   - Multi-video autonomous farm surveillance feeds:
     1. Autonomous Drone Aerial Scan (1080p, 5-band red-edge)
     2. Plant Growth & Cell Phenotype Development Timelapse
     3. NRCS Vadose Irrigation & Water Jet Dynamics
     4. Fleet Autonomous Combine Harvester Operations
   - Real-time agricultural vision HUD with bounding boxes & radar sweep
   - Circular SVG radial gauges for soil moisture & biophysical metrics
   - AgriBrain AI Copilot with interactive prompt chips & fleet dispatch
   - Complete preservation of all MESIA R2 deep-tech biophysical content
   ═══════════════════════════════════════════════════════════════ */

interface VideoStream {
  id: "drone" | "growth" | "irrigation" | "harvest";
  title: string;
  badge: string;
  src: string;
  camInfo: string;
  streamQuality: string;
  hudTopLeft: string;
  gpsCoords: string;
  box1Title: string;
  box1Desc: string;
  box1Color: string;
  box2Title: string;
  box2Desc: string;
  box2Color: string;
}

const VIDEO_STREAMS: VideoStream[] = [
  {
    id: "drone",
    title: "Canola Aerial Scan",
    badge: "CANOPY RECONNAISSANCE",
    src: "/videos/drone-field-scan.webm",
    camInfo: "CAM: 5-BAND RED-EDGE MULTISPECTRAL",
    streamQuality: "STREAM: 60 FPS · 1080P STABILIZED",
    hudTopLeft: "ALT: 38.5M · SPEED: 7.2 M/S · FOV: 84°",
    gpsCoords: "GPS: 48.1351° N, 11.5820° E",
    box1Title: "[CANOPY BLOOM DENSITY]",
    box1Desc: "NDVI: 0.86 · Vegetative Index Optimal",
    box1Color: "#00E676",
    box2Title: "[BIOMASS ACCUMULATION]",
    box2Desc: "Estimated Yield: 4.6 t/ha · Zero Lodging",
    box2Color: "#F59E0B",
  },
  {
    id: "growth",
    title: "Phenotype Growth",
    badge: "BIOLOGICAL DYNAMICS",
    src: "/videos/crop-growth-timelapse.webm",
    camInfo: "OPTICS: IN SITU PHENOTYPING",
    streamQuality: "TIMELAPSE: 1 FRAME / 30 MIN",
    hudTopLeft: "STAGE: ANTHESIS TO FRUIT EXPANSION",
    gpsCoords: "PLOT: PRECISION HORTICULTURE CELL",
    box1Title: "[FLOWERING TO FRUIT SET]",
    box1Desc: "Cell Expansion Rate: +14.2% / 24h",
    box1Color: "#00D9FF",
    box2Title: "[TRANSPIRATION BALANCE]",
    box2Desc: "Photosynthetic Flux: 22.4 µmol CO₂/m²·s",
    box2Color: "#00E676",
  },
  {
    id: "irrigation",
    title: "Center Pivot Flux",
    badge: "PRECISION IRRIGATION",
    src: "/videos/irrigation-water-flux.webm",
    camInfo: "SENSOR: CENTER PIVOT SCADA TELEMETRY",
    streamQuality: "TELEMETRY: DYNAMIC FLUX 100 Hz",
    hudTopLeft: "SPAN: 380M CIRCULAR · SPEED: 1.8 M/MIN",
    gpsCoords: "PIVOT SECTOR: AZIMUTH 142°",
    box1Title: "[VADOSE INFILTRATION BOUNDARY]",
    box1Desc: "Richards Darcy Infiltration: 18.4 mm/h",
    box1Color: "#00D9FF",
    box2Title: "[AQUIFER CONSERVATION GAIN]",
    box2Desc: "Capillary Retention: 94.2% · Drawdown -31.8%",
    box2Color: "#34D399",
  },
  {
    id: "harvest",
    title: "Fleet Harvester Tandem",
    badge: "AUTONOMOUS OPERATIONS",
    src: "/videos/autonomous-harvest.webm",
    camInfo: "FLEET: TANDEM COMBINE & CHASER BIN",
    streamQuality: "GNSS RTK PRECISION: ±1.2 CM",
    hudTopLeft: "SWATH: 10.5M · SPEED: 6.5 KM/H · GRAIN TANK: 78%",
    gpsCoords: "PARCEL: SECTOR J-402 TRACT",
    box1Title: "[GRAIN YIELD SENSOR ACCURACY]",
    box1Desc: "Real-Time Yield: 8.84 t/ha · Moisture 13.4%",
    box1Color: "#F59E0B",
    box2Title: "[AUTONOMOUS FLEET SYNC]",
    box2Desc: "Chaser Tractor Synchronized · Zero Spillage",
    box2Color: "#00E676",
  },
];

const DEFAULT_RESPONSES: Record<Locale, {
  time: string;
  tag: string;
  text: string;
  formula?: string;
}> = {
  en: {
    time: "08:42",
    tag: "ASMAE BIOPHYSICAL INVERSION",
    text: "Vapor Pressure Deficit (1.42 kPa) exceeds capillary suction in sandy loam horizon at -40cm. Stomatal transpiration throttling imminent within 14h.",
    formula: "∂θ/∂t = ∇·(K(ψ)∇(ψ+z)) - S(z,t)",
  },
  ar: {
    time: "08:42",
    tag: "انعكاس فيزيائي حيوي ASMAE",
    text: "عجز ضغط البخار (1.42 كيلو باسكال) يتجاوز الامتصاص الشعري في أفق الطمي الرملي عند عمق -40 سم. خنق نتح الثغور وشيك خلال 14 ساعة.",
    formula: "∂θ/∂t = ∇·(K(ψ)∇(ψ+z)) - S(z,t)",
  },
  fr: {
    time: "08:42",
    tag: "INVERSION BIOPHYSIQUE ASMAE",
    text: "Le déficit de pression de vapeur (1,42 kPa) dépasse la succion capillaire dans l'horizon limono-sableux à -40 cm. Régulation de la transpiration stomatique imminente sous 14h.",
    formula: "∂θ/∂t = ∇·(K(ψ)∇(ψ+z)) - S(z,t)",
  },
};

const PROMPT_SCENARIOS: Record<"rain" | "fertigation" | "vadose", Record<Locale, {
  tag: string;
  text: string;
  formula: string;
}>> = {
  rain: {
    en: {
      tag: "COUNTERFACTUAL CLIMATE SHOCK",
      text: "Under -30% precipitation, root zone matric suction drops to -68 kPa in Durum Wheat by Day 18. Supplemental 18mm pulse stabilizes yield at 96.4% Pareto frontier.",
      formula: "P(Yield | do(Rain = -30%), Fertigation = +18mm) = 0.964",
    },
    ar: {
      tag: "صدمة مناخية مضادة للواقع",
      text: "في ظل انخفاض هطول الأمطار بنسبة 30%، ينخفض الشفط الماتريسي لمنطقة الجذور إلى -68 كيلو باسكال في القمح الصلب بحلول اليوم 18. نبضة تكميلية قدرها 18 ملم تثبت الإنتاجية عند جبهة باريتو 96.4%.",
      formula: "P(Yield | do(Rain = -30%), Fertigation = +18mm) = 0.964",
    },
    fr: {
      tag: "CHOC CLIMATIQUE CONTREFACTUEL",
      text: "Sous -30% de précipitations, l'aspiration matricielle racinaire chute à -68 kPa sur le blé dur au jour 18. Une impulsion d'appoint de 18 mm stabilise le rendement à 96,4% sur la frontière de Pareto.",
      formula: "P(Yield | do(Rain = -30%), Fertigation = +18mm) = 0.964",
    },
  },
  fertigation: {
    en: {
      tag: "OFF-PEAK FERTIGATION POLICY",
      text: "Off-peak window tonight (22:00–02:00) provides 4.2x higher transpiration efficiency with 0 nitrate runoff. Energy cost: $0.038/kWh. Conserves 16,500L water.",
      formula: "J_solute = -D_e(∂C/∂z) + q_Darcy · C",
    },
    ar: {
      tag: "سياسة التسميد بالري خارج أوقات الذروة",
      text: "نافذة الري خارج أوقات الذروة الليلة (22:00–02:00) توفر كفاءة نتح أعلى بمقدار 4.2 ضعفًا دون أي جريان للنترات. تكلفة الطاقة: 0.038 دولار/كيلوواط ساعة. توفير 16,500 لتر من المياه.",
      formula: "J_solute = -D_e(∂C/∂z) + q_Darcy · C",
    },
    fr: {
      tag: "POLITIQUE DE FERTIRRIGATION HEURES CREUSES",
      text: "La fenêtre d'heures creuses cette nuit (22h00–02h00) offre une efficacité de transpiration 4,2x supérieure sans ruissellement de nitrate. Coût énergétique: 0,038 $/kWh. Économise 16 500L d'eau.",
      formula: "J_solute = -D_e(∂C/∂z) + q_Darcy · C",
    },
  },
  vadose: {
    en: {
      tag: "MAXWELL DIELECTRIC INVERSION",
      text: "Complex permittivity ε* = 18.4 - 3.2j across 0–120cm depth profile. Inverting Richards equation indicates active capillary rise supplying 2.1 mm/day from water table.",
      formula: "ε_eff = θ·ε_water + (1-Φ)·ε_soil + (Φ-θ)·ε_air",
    },
    ar: {
      tag: "انعكاس ماكسويل العازل للكهرباء",
      text: "السماحية المعقدة ε* = 18.4 - 3.2j عبر مقطع عمق 0-120 سم. يشير حل معادلة ريتشاردز العكسية إلى صعود شعري نشط يمد 2.1 ملم/يوم من منسوب المياه الجوفية.",
      formula: "ε_eff = θ·ε_water + (1-Φ)·ε_soil + (Φ-θ)·ε_air",
    },
    fr: {
      tag: "INVERSION DIÉLECTRIQUE DE MAXWELL",
      text: "Permittivité complexe ε* = 18,4 - 3,2j sur le profil 0–120cm. L'inversion de l'équation de Richards indique une remontée capillaire active de 2,1 mm/jour depuis la nappe.",
      formula: "ε_eff = θ·ε_water + (1-Φ)·ε_soil + (Φ-θ)·ε_air",
    },
  },
};

export default function HomeHero() {
  const { t, isRtl, locale } = useLanguage();
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [isMuted, setIsMuted] = useState<boolean>(true);
  const [videoMode, setVideoMode] = useState<"rgb" | "ndvi" | "vadose">("rgb");
  const [selectedStreamIndex, setSelectedStreamIndex] = useState<number>(0);
  const [isDispatched, setIsDispatched] = useState<boolean>(false);
  const [copilotQuery, setCopilotQuery] = useState<string>("");
  const [copilotResponse, setCopilotResponse] = useState<{
    time: string;
    tag: string;
    text: string;
    formula?: string;
  }>(DEFAULT_RESPONSES.en);

  // Synchronize copilot initial response when locale changes
  useEffect(() => {
    setCopilotResponse(DEFAULT_RESPONSES[locale] || DEFAULT_RESPONSES.en);
  }, [locale]);

  const videoRef = useRef<HTMLVideoElement>(null);
  const activeStream = VIDEO_STREAMS[selectedStreamIndex];
  const streamI18n = t.hero.streams[activeStream.id];

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !videoRef.current.muted;
    setIsMuted(videoRef.current.muted);
  };

  const handleDispatch = () => {
    setIsDispatched(true);
    setTimeout(() => setIsDispatched(false), 4000);
  };

  const handlePromptClick = (key: "rain" | "fertigation" | "vadose", labelText: string) => {
    setCopilotQuery(labelText);
    const scenario = PROMPT_SCENARIOS[key][locale] || PROMPT_SCENARIOS[key].en;
    setCopilotResponse({
      time: locale === "ar" ? "الآن" : locale === "fr" ? "À L'INSTANT" : "JUST NOW",
      tag: scenario.tag,
      text: scenario.text,
      formula: scenario.formula,
    });
  };

  const handleCustomQuerySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!copilotQuery.trim()) return;
    const localizedInversion =
      locale === "ar"
        ? `حل الواقع الفيزيائي الحيوي لـ "${copilotQuery}": تم استيفاء قيود الحدود. المتبقي من حفظ الكتلة < 0.012 كيلو باسكال عبر خط العالم النشط.`
        : locale === "fr"
        ? `Inversion de la réalité biophysique pour "${copilotQuery}": Contraintes aux limites satisfaites. Résidu de conservation de masse < 0.012 kPa sur la ligne d'univers active.`
        : `Inverting biophysical reality for "${copilotQuery}": Boundary constraints satisfied. Mass conservation residual < 0.012 kPa across active PlotWorldline.`;

    setCopilotResponse({
      time: locale === "ar" ? "الآن" : locale === "fr" ? "À L'INSTANT" : "JUST NOW",
      tag: "AGRIBRAIN MESIA R2 CAUSAL INFERENCE",
      text: localizedInversion,
      formula: "P(Sovereign Yield | do(Policy), E_observed)",
    });
  };

  return (
    <section
      id="hero"
      className="deep-tech-lattice"
      style={{
        position: "relative",
        minHeight: "96vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        paddingTop: "96px",
        paddingBottom: "80px",
        overflow: "hidden",
        background: "radial-gradient(ellipse at 50% 10%, #081a10 0%, #030805 80%)",
      }}
    >
      {/* Ambient glowing emerald backlight bloom */}
      <div
        style={{
          position: "absolute",
          top: "2%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "1300px",
          height: "550px",
          background: "radial-gradient(ellipse, rgba(34, 197, 94, 0.12) 0%, transparent 72%)",
          pointerEvents: "none",
        }}
      />

      <div className="marketing-container" style={{ position: "relative", zIndex: 10 }}>
        {/* 1. HERO BRAND & EMBLEM SHOWCASE */}
        <div style={{ textAlign: "center", marginBottom: "20px" }}>
          <div
            style={{
              display: "inline-flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {/* Clean Floating AgriWise Logo (Borders & Container Box Removed) */}
            <div
              style={{
                position: "relative",
                display: "inline-block",
                marginBottom: "12px",
              }}
            >
              <Image
                src="/logo-dark.png"
                alt="AgriWise Intelligence Infrastructure"
                width={440}
                height={280}
                style={{
                  height: "clamp(120px, 18vw, 172px)",
                  width: "auto",
                  objectFit: "contain",
                  display: "block",
                  filter: "drop-shadow(0 0 45px rgba(34, 197, 94, 0.4))",
                }}
                priority
              />
            </div>

            {/* Sub-badge with Musemind style pulse */}
            <div
              className="fiducial-badge emerald-pulse-badge"
              style={{
                marginTop: "2px",
                padding: "6px 16px",
                fontSize: "11px",
                letterSpacing: isRtl ? "0" : "0.12em",
                background: "rgba(34, 197, 94, 0.08)",
                borderColor: "rgba(34, 197, 94, 0.3)",
                transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            >
              <span className="pulse-dot" style={{ backgroundColor: "#22c55e" }} />
              <span style={{ color: "#86efac", fontWeight: 700 }}>{t.hero.slogan}</span>
            </div>
          </div>
        </div>

        {/* 2. MAJESTIC HEADLINE & NARRATIVE */}
        <div style={{ maxWidth: "980px", margin: "0 auto 28px", textAlign: "center" }}>
          <h1
            className="apple-hero-headline font-heading"
            style={{
              fontSize: "clamp(2.7rem, 5.8vw, 4.8rem)",
              fontWeight: 800,
              lineHeight: isRtl ? 1.25 : 1.04,
              letterSpacing: isRtl ? "0" : "-0.035em",
              color: "#ffffff",
              margin: "0 0 18px",
            }}
          >
            {t.hero.headlineMain} <br />
            <span
              className="text-gradient-emerald"
              style={{
                filter: "drop-shadow(0 0 35px rgba(34, 197, 94, 0.35))",
                display: "inline-block",
              }}
            >
              {t.hero.headlineAccent}
            </span>
          </h1>

          <p
            style={{
              fontSize: "clamp(16px, 1.9vw, 20px)",
              fontWeight: 400,
              color: "#cbd5e1",
              lineHeight: 1.6,
              margin: "0 auto 28px",
              maxWidth: "780px",
            }}
          >
            {t.hero.subheadline}
          </p>

          {/* Action CTAs */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "16px",
              flexWrap: "wrap",
            }}
          >
            <a
              href="#perception"
              className="hover-lift"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "14px 32px",
                borderRadius: "10px",
                background: "#22c55e",
                color: "#05070B",
                fontSize: "14px",
                fontWeight: 700,
                textDecoration: "none",
                boxShadow: "0 0 35px rgba(34, 197, 94, 0.45)",
              }}
            >
              <span>{t.hero.exploreCognitiveLoop}</span>
              <ArrowRight
                size={17}
                style={{
                  transform: isRtl ? "rotate(180deg)" : "none",
                  transition: "transform 0.2s ease",
                }}
              />
            </a>

            <a
              href="#reasoning"
              className="hover-lift"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "14px 28px",
                borderRadius: "10px",
                background: "rgba(255, 255, 255, 0.04)",
                border: "1px solid rgba(34, 197, 94, 0.3)",
                color: "#ffffff",
                fontSize: "14px",
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              <span>{t.hero.simulateCounterfactuals}</span>
            </a>
          </div>
        </div>

        {/* 3. DRIBBBLE-STYLE AI-POWERED FARMING DASHBOARD COCKPIT (MUSEMIND AGRIXAI STANDARD) */}
        <div
          className="dribbble-glass-card"
          style={{
            maxWidth: "1160px",
            margin: "0 auto",
            borderRadius: "22px",
            overflow: "hidden",
          }}
        >
          {/* Top Dashboard Cockpit Status Bar */}
          <div
            style={{
              padding: "12px 20px",
              background: "rgba(4, 12, 8, 0.95)",
              borderBottom: "1px solid rgba(34, 197, 94, 0.18)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            {/* Left: Live Stream Indicator & Parcel Badge */}
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "7px",
                  padding: "4px 10px",
                  borderRadius: "6px",
                  background: "rgba(34, 197, 94, 0.15)",
                  border: "1px solid rgba(34, 197, 94, 0.4)",
                  color: "#22c55e",
                  fontSize: "11px",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 700,
                }}
              >
                <span className="pulse-dot" style={{ width: "6px", height: "6px", backgroundColor: "#22c55e" }} />
                <span>LIVE {streamI18n.badge}</span>
              </div>
              <div style={{ fontSize: "12px", color: "#F8FAFC", fontWeight: 600 }}>
                {t.hero.plotSector}
              </div>
            </div>

            {/* Center: Active World Model */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "11px",
                fontFamily: "var(--font-mono)",
                color: "#94A3B8",
              }}
            >
              <Cpu size={14} style={{ color: "#22c55e" }} />
              <span>{t.hero.foundationModel}</span>
            </div>

            {/* Right: Real-time Weather Telemetry Pill */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "14px",
                fontSize: "11px",
                fontFamily: "var(--font-mono)",
                color: "#CBD5E1",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <Sun size={13} style={{ color: "#F59E0B" }} /> 24.5°C
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <Droplets size={13} style={{ color: "#00D9FF" }} /> 1.4 kPa {t.hero.vpdText}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <Wind size={13} style={{ color: "#818CF8" }} /> 6.4 km/h {t.hero.windText}
              </span>
            </div>
          </div>

          {/* Stream Selector Navigation Strip (4 Real Video Feeds) */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 18px",
              background: "rgba(5, 14, 9, 0.9)",
              borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
              overflowX: "auto",
            }}
          >
            <span
              style={{
                fontSize: "10px",
                fontFamily: "var(--font-mono)",
                color: "#64748B",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginInlineEnd: "6px",
                whiteSpace: "nowrap",
              }}
            >
              {t.hero.surveillanceStream}:
            </span>

            {VIDEO_STREAMS.map((stream, idx) => (
              <button
                key={stream.id}
                onClick={() => setSelectedStreamIndex(idx)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "5px 12px",
                  borderRadius: "8px",
                  background:
                    selectedStreamIndex === idx
                      ? "rgba(34, 197, 94, 0.22)"
                      : "rgba(255, 255, 255, 0.03)",
                  border:
                    selectedStreamIndex === idx
                      ? "1px solid #22c55e"
                      : "1px solid rgba(255, 255, 255, 0.08)",
                  color: selectedStreamIndex === idx ? "#22c55e" : "#94A3B8",
                  fontSize: "11px",
                  fontFamily: "var(--font-mono)",
                  fontWeight: selectedStreamIndex === idx ? 700 : 500,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  transition: "all 0.2s ease",
                }}
              >
                <span
                  style={{
                    width: "5px",
                    height: "5px",
                    borderRadius: "50%",
                    backgroundColor: selectedStreamIndex === idx ? "#22c55e" : "#64748B",
                  }}
                />
                <span>{t.hero.streams[stream.id]?.title || stream.title}</span>
              </button>
            ))}
          </div>

          {/* Main Dashboard Stage: Video Viewport & AI Reasoning Sidebar */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.32fr 0.68fr",
              borderBottom: "1px solid rgba(34, 197, 94, 0.15)",
            }}
            className="cockpit-main-grid"
          >
            {/* Left: High-Definition Video Flight / Surveillance Stream */}
            <div
              style={{
                position: "relative",
                minHeight: "450px",
                background: "#020704",
                overflow: "hidden",
              }}
            >
              {/* Radar Sweep Animated Laser Line */}
              <div className="radar-scanline" />

              {/* HTML5 Native Video Player */}
              <video
                key={activeStream.src}
                ref={videoRef}
                src={activeStream.src}
                autoPlay
                loop
                muted={isMuted}
                playsInline
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  display: "block",
                  filter:
                    videoMode === "ndvi"
                      ? "hue-rotate(95deg) contrast(1.4) saturate(2)"
                      : videoMode === "vadose"
                      ? "sepia(0.85) hue-rotate(180deg) contrast(1.6)"
                      : "none",
                  transition: "filter 0.4s ease",
                }}
              />

              {/* Corner HUD Reticle Brackets */}
              <div
                style={{
                  position: "absolute",
                  top: "14px",
                  left: "14px",
                  width: "20px",
                  height: "20px",
                  borderTop: "2px solid #22c55e",
                  borderLeft: "2px solid #22c55e",
                  pointerEvents: "none",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  top: "14px",
                  right: "14px",
                  width: "20px",
                  height: "20px",
                  borderTop: "2px solid #22c55e",
                  borderRight: "2px solid #22c55e",
                  pointerEvents: "none",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  bottom: "54px",
                  left: "14px",
                  width: "20px",
                  height: "20px",
                  borderBottom: "2px solid #22c55e",
                  borderLeft: "2px solid #22c55e",
                  pointerEvents: "none",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  bottom: "54px",
                  right: "14px",
                  width: "20px",
                  height: "20px",
                  borderBottom: "2px solid #22c55e",
                  borderRight: "2px solid #22c55e",
                  pointerEvents: "none",
                }}
              />

              {/* HUD Flight Telemetry Overlay */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  pointerEvents: "none",
                  padding: "16px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                {/* Top Telemetry Strip */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div
                    style={{
                      background: "rgba(4, 12, 8, 0.85)",
                      backdropFilter: "blur(14px)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "8px",
                      padding: "6px 12px",
                      fontSize: "10px",
                      fontFamily: "var(--font-mono)",
                      color: "#FFFFFF",
                    }}
                  >
                    <div>{activeStream.hudTopLeft}</div>
                    <div style={{ color: "#00D9FF", marginTop: "2px" }}>{activeStream.gpsCoords}</div>
                  </div>

                  <div
                    style={{
                      background: "rgba(4, 12, 8, 0.85)",
                      backdropFilter: "blur(14px)",
                      border: "1px solid rgba(34, 197, 94, 0.35)",
                      borderRadius: "8px",
                      padding: "6px 12px",
                      fontSize: "10px",
                      fontFamily: "var(--font-mono)",
                      color: "#22c55e",
                      textAlign: "right",
                    }}
                  >
                    <div>{activeStream.camInfo}</div>
                    <div style={{ color: "#94A3B8", marginTop: "2px" }}>{activeStream.streamQuality}</div>
                  </div>
                </div>

                {/* Center AI Target Reticles & Bounding Boxes */}
                <div style={{ position: "relative", height: "180px" }}>
                  {/* Rotating Reticle Crosshair with Concentric Radar Ping */}
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      transform: "translate(-50%, -50%)",
                      width: "64px",
                      height: "64px",
                      pointerEvents: "none",
                    }}
                  >
                    {/* Concentric expanding ping ring */}
                    <div className="radar-ping-ring" />
                    <div
                      style={{
                        width: "100%",
                        height: "100%",
                        border: "1px dashed rgba(34, 197, 94, 0.55)",
                        borderRadius: "50%",
                        animation: "reticle-spin 14s linear infinite",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <div
                        style={{
                          width: "7px",
                          height: "7px",
                          borderRadius: "50%",
                          backgroundColor: "#22c55e",
                          boxShadow: "0 0 12px #22c55e, 0 0 4px #4ade80",
                        }}
                      />
                    </div>
                  </div>

                  {/* Bounding Box 1 */}
                  <div
                    style={{
                      position: "absolute",
                      top: "16%",
                      left: "10%",
                      width: "200px",
                      border: `1px solid ${activeStream.box1Color}`,
                      borderRadius: "6px",
                      padding: "6px 10px",
                      background: "rgba(4, 16, 9, 0.65)",
                      backdropFilter: "blur(6px)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "9px",
                        fontFamily: "var(--font-mono)",
                        color: activeStream.box1Color,
                        fontWeight: 700,
                      }}
                    >
                      {streamI18n.box1Title}
                    </div>
                    <div style={{ fontSize: "11px", fontWeight: 700, color: "#FFFFFF" }}>
                      {streamI18n.box1Desc}
                    </div>
                  </div>

                  {/* Bounding Box 2 */}
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      right: "12%",
                      width: "220px",
                      border: `1px solid ${activeStream.box2Color}`,
                      borderRadius: "6px",
                      padding: "6px 10px",
                      background: "rgba(16, 12, 4, 0.65)",
                      backdropFilter: "blur(6px)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "9px",
                        fontFamily: "var(--font-mono)",
                        color: activeStream.box2Color,
                        fontWeight: 700,
                      }}
                    >
                      {streamI18n.box2Title}
                    </div>
                    <div style={{ fontSize: "11px", fontWeight: 700, color: "#FFFFFF" }}>
                      {streamI18n.box2Desc}
                    </div>
                  </div>
                </div>

                {/* Bottom Video Controls & Layer Switcher */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    pointerEvents: "auto",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <button
                      onClick={togglePlay}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        background: "rgba(4, 12, 8, 0.88)",
                        backdropFilter: "blur(12px)",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "8px",
                        padding: "6px 14px",
                        color: "#FFFFFF",
                        fontSize: "11px",
                        fontFamily: "var(--font-mono)",
                        cursor: "pointer",
                      }}
                    >
                      {isPlaying ? <Pause size={12} /> : <Play size={12} />}
                      <span>
                        {isPlaying
                          ? locale === "ar"
                            ? "إيقاف مؤقت"
                            : locale === "fr"
                            ? "PAUSE"
                            : "PAUSE"
                          : locale === "ar"
                          ? "تشغيل"
                          : locale === "fr"
                          ? "LECTURE"
                          : "PLAY"}
                      </span>
                    </button>

                    <button
                      onClick={toggleMute}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        background: "rgba(4, 12, 8, 0.88)",
                        backdropFilter: "blur(12px)",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "8px",
                        padding: "6px 10px",
                        color: "#FFFFFF",
                        fontSize: "11px",
                        cursor: "pointer",
                      }}
                      title={isMuted ? "Unmute" : "Mute"}
                    >
                      {isMuted ? <VolumeX size={12} /> : <Volume2 size={12} />}
                    </button>
                  </div>

                  {/* Spectral Filter Toggle */}
                  <div
                    style={{
                      display: "inline-flex",
                      background: "rgba(4, 12, 8, 0.88)",
                      backdropFilter: "blur(12px)",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "8px",
                      padding: "3px",
                      gap: "4px",
                    }}
                  >
                    {(
                      [
                        {
                          id: "rgb" as const,
                          label: locale === "ar" ? "بصري RGB" : locale === "fr" ? "Optique RVB" : "Optical RGB",
                        },
                        {
                          id: "ndvi" as const,
                          label: locale === "ar" ? "طيفي NDVI" : locale === "fr" ? "NDVI Thermique" : "NDVI Thermal",
                        },
                        {
                          id: "vadose" as const,
                          label:
                            locale === "ar"
                              ? "رادار النطاق الهوائي (-120 سم)"
                              : locale === "fr"
                              ? "Radar Vadose (-120cm)"
                              : "Vadose Radar (-120cm)",
                        },
                      ] as const
                    ).map((mode) => (
                      <button
                        key={mode.id}
                        onClick={() => setVideoMode(mode.id)}
                        style={{
                          background: videoMode === mode.id ? "rgba(34, 197, 94, 0.25)" : "transparent",
                          border: videoMode === mode.id ? "1px solid #22c55e" : "1px solid transparent",
                          color: videoMode === mode.id ? "#22c55e" : "#94A3B8",
                          borderRadius: "6px",
                          padding: "4px 10px",
                          fontSize: "10px",
                          fontFamily: "var(--font-mono)",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        {mode.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Right: AgriBrain AI Copilot & Causal Dispatch Sidebar */}
            <div
              style={{
                background: "rgba(6, 18, 12, 0.96)",
                padding: "20px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                borderInlineStart: "1px solid rgba(34, 197, 94, 0.18)",
              }}
            >
              <div>
                {/* Copilot Header */}
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                  <div
                    style={{
                      width: "36px",
                      height: "36px",
                      borderRadius: "10px",
                      background: "rgba(34, 197, 94, 0.18)",
                      border: "1px solid rgba(34, 197, 94, 0.45)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#22c55e",
                    }}
                  >
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <div style={{ fontSize: "14px", fontWeight: 700, color: "#FFFFFF" }}>
                      {t.hero.copilotTitle}
                    </div>
                    <div style={{ fontSize: "11px", color: "#22c55e", fontFamily: "var(--font-mono)" }}>
                      {t.hero.copilotSubtitle}
                    </div>
                  </div>
                </div>

                {/* Quick Simulation Scenario Pills */}
                <div style={{ marginBottom: "14px" }}>
                  <div
                    style={{
                      fontSize: "10px",
                      fontFamily: "var(--font-mono)",
                      color: "#64748B",
                      marginBottom: "6px",
                      textTransform: "uppercase",
                    }}
                  >
                    {t.hero.scenarioChipsLabel}:
                  </div>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                    {[
                      { key: "rain" as const, label: t.hero.chipRain },
                      { key: "fertigation" as const, label: t.hero.chipFertigation },
                      { key: "vadose" as const, label: t.hero.chipVadose },
                    ].map((chip) => (
                      <button
                        key={chip.key}
                        onClick={() => handlePromptClick(chip.key, chip.label)}
                        style={{
                          background: "rgba(255, 255, 255, 0.04)",
                          border: "1px solid rgba(34, 197, 94, 0.25)",
                          borderRadius: "6px",
                          padding: "4px 8px",
                          fontSize: "10px",
                          fontFamily: "var(--font-mono)",
                          color: "#86efac",
                          cursor: "pointer",
                          transition: "all 0.2s ease",
                        }}
                      >
                        +{chip.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Live Causal AI Dispatch Message Stream */}
                <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "16px" }}>
                  <div
                    style={{
                      background: "rgba(0, 0, 0, 0.45)",
                      border: "1px solid rgba(34, 197, 94, 0.2)",
                      borderRadius: "10px",
                      padding: "12px 14px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "9px",
                        color: "#22c55e",
                        fontFamily: "var(--font-mono)",
                        marginBottom: "4px",
                        fontWeight: 700,
                      }}
                    >
                      {copilotResponse.time} · {copilotResponse.tag}
                    </div>
                    <p style={{ fontSize: "12px", color: "#E2E8F0", lineHeight: 1.45, margin: "0 0 6px" }}>
                      {copilotResponse.text}
                    </p>
                    {copilotResponse.formula && (
                      <div
                        style={{
                          fontSize: "10px",
                          fontFamily: "var(--font-mono)",
                          color: "#00D9FF",
                          background: "rgba(0, 217, 255, 0.08)",
                          padding: "3px 6px",
                          borderRadius: "4px",
                          display: "inline-block",
                          direction: "ltr",
                          unicodeBidi: "isolate",
                        }}
                      >
                        {copilotResponse.formula}
                      </div>
                    )}
                  </div>
                </div>

                {/* Natural Language Query Bar */}
                <form onSubmit={handleCustomQuerySubmit} style={{ position: "relative", marginBottom: "14px" }}>
                  <input
                    type="text"
                    value={copilotQuery}
                    onChange={(e) => setCopilotQuery(e.target.value)}
                    placeholder={t.hero.inputPlaceholder}
                    style={{
                      width: "100%",
                      paddingInlineStart: "12px",
                      paddingInlineEnd: "36px",
                      paddingTop: "9px",
                      paddingBottom: "9px",
                      borderRadius: "8px",
                      background: "rgba(0, 0, 0, 0.5)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      color: "#FFFFFF",
                      fontSize: "11px",
                      fontFamily: "var(--font-mono)",
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                  <button
                    type="submit"
                    style={{
                      position: "absolute",
                      insetInlineEnd: "8px",
                      top: "50%",
                      transform: isRtl ? "translateY(-50%) scaleX(-1)" : "translateY(-50%)",
                      background: "transparent",
                      border: "none",
                      color: "#22c55e",
                      cursor: "pointer",
                      padding: "4px",
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    <Send size={13} />
                  </button>
                </form>
              </div>

              {/* Action Buttons */}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <button
                  onClick={handleDispatch}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "8px",
                    padding: "11px 16px",
                    borderRadius: "10px",
                    background: isDispatched ? "rgba(34, 197, 94, 0.25)" : "#22c55e",
                    border: isDispatched ? "1px solid #22c55e" : "none",
                    color: isDispatched ? "#22c55e" : "#05070B",
                    fontSize: "12px",
                    fontWeight: 700,
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  <Send size={13} style={{ transform: isRtl ? "scaleX(-1)" : "none" }} />
                  <span>{isDispatched ? t.hero.dispatchedBtn : t.hero.dispatchBtn}</span>
                </button>

                <a
                  href="#reasoning"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    padding: "9px 14px",
                    borderRadius: "10px",
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    color: "#CBD5E1",
                    fontSize: "11px",
                    fontFamily: "var(--font-mono)",
                    textDecoration: "none",
                    textAlign: "center",
                  }}
                >
                  <span>{t.hero.simulate72h}</span>
                  <ArrowRight
                    size={13}
                    style={{
                      transform: isRtl ? "rotate(180deg)" : "none",
                      transition: "transform 0.2s ease",
                    }}
                  />
                </a>
              </div>
            </div>
          </div>

          {/* Bottom 4 Bento Metric Cards with Musemind Circular Radial Gauges */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              background: "rgba(4, 12, 8, 0.88)",
            }}
            className="cockpit-bento-grid"
          >
            {/* Card 1: Soil Moisture & Vadose Strata */}
            <div
              className="hover-lift transition-smooth"
              style={{
                padding: "18px 20px",
                borderInlineEnd: "1px solid rgba(34, 197, 94, 0.15)",
                display: "flex",
                alignItems: "center",
                gap: "14px",
                cursor: "default",
              }}
            >
              {/* Circular Radial Gauge */}
              <div style={{ position: "relative", width: "52px", height: "52px", flexShrink: 0 }}>
                <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="3.5"
                  />
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="#22c55e"
                    strokeWidth="3.5"
                    strokeDasharray="72, 100"
                    strokeLinecap="round"
                    style={{
                      transition: "stroke-dasharray 1s ease",
                      filter: "drop-shadow(0 0 6px rgba(34, 197, 94, 0.5))",
                    }}
                  />
                </svg>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "11px",
                    fontWeight: 800,
                    fontFamily: "var(--font-mono)",
                    color: "#22c55e",
                  }}
                >
                  72%
                </div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                  <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "#94A3B8" }}>
                    {t.hero.vadoseMoisture}
                  </span>
                  <span
                    style={{
                      fontSize: "8px",
                      fontFamily: "var(--font-mono)",
                      color: "#22c55e",
                      background: "rgba(34, 197, 94, 0.15)",
                      padding: "1px 5px",
                      borderRadius: "4px",
                      fontWeight: 700,
                    }}
                  >
                    {t.hero.optimalBadge}
                  </span>
                </div>
                <div
                  className="font-heading"
                  style={{ fontSize: "22px", fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em" }}
                >
                  28.4% <span style={{ fontSize: "12px", color: "#94A3B8", fontWeight: 500, fontFamily: "var(--font-mono)" }}>VWC</span>
                </div>
                <div style={{ fontSize: "10px", color: "#86efac", marginTop: "2px" }}>
                  Depth: -120cm · Depletion 3.8 mm/d
                </div>
              </div>
            </div>

            {/* Card 2: Canopy Transpiration Flux */}
            <div
              className="hover-lift transition-smooth"
              style={{
                padding: "18px 20px",
                borderInlineEnd: "1px solid rgba(34, 197, 94, 0.15)",
                display: "flex",
                alignItems: "center",
                gap: "14px",
                cursor: "default",
              }}
            >
              {/* Circular Radial Gauge */}
              <div style={{ position: "relative", width: "52px", height: "52px", flexShrink: 0 }}>
                <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="3.5"
                  />
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="#00D9FF"
                    strokeWidth="3.5"
                    strokeDasharray="84, 100"
                    strokeLinecap="round"
                    style={{
                      transition: "stroke-dasharray 1s ease",
                      filter: "drop-shadow(0 0 6px rgba(0, 217, 255, 0.5))",
                    }}
                  />
                </svg>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "11px",
                    fontWeight: 800,
                    fontFamily: "var(--font-mono)",
                    color: "#00D9FF",
                  }}
                >
                  84%
                </div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                  <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "#94A3B8" }}>
                    {t.hero.transpirationFlux}
                  </span>
                  <span
                    style={{
                      fontSize: "8px",
                      fontFamily: "var(--font-mono)",
                      color: "#00D9FF",
                      background: "rgba(0, 217, 255, 0.15)",
                      padding: "1px 5px",
                      borderRadius: "4px",
                      fontWeight: 700,
                    }}
                  >
                    {t.hero.noStressBadge}
                  </span>
                </div>
                <div
                  className="font-heading"
                  style={{ fontSize: "22px", fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em" }}
                >
                  4.2 <span style={{ fontSize: "12px", color: "#94A3B8", fontWeight: 500, fontFamily: "var(--font-mono)" }}>mm/day</span>
                </div>
                <div style={{ fontSize: "10px", color: "#00D9FF", marginTop: "2px" }}>
                  Stomatal Conductance Free
                </div>
              </div>
            </div>

            {/* Card 3: PlotWorldline Learned Prior */}
            <div
              className="hover-lift transition-smooth"
              style={{
                padding: "18px 20px",
                borderInlineEnd: "1px solid rgba(34, 197, 94, 0.15)",
                display: "flex",
                alignItems: "center",
                gap: "14px",
                cursor: "default",
              }}
            >
              {/* Circular Radial Gauge */}
              <div style={{ position: "relative", width: "52px", height: "52px", flexShrink: 0 }}>
                <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="3.5"
                  />
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="#A78BFA"
                    strokeWidth="3.5"
                    strokeDasharray="92, 100"
                    strokeLinecap="round"
                    style={{
                      transition: "stroke-dasharray 1s ease",
                      filter: "drop-shadow(0 0 6px rgba(167, 139, 250, 0.5))",
                    }}
                  />
                </svg>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "11px",
                    fontWeight: 800,
                    fontFamily: "var(--font-mono)",
                    color: "#A78BFA",
                  }}
                >
                  92%
                </div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                  <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "#94A3B8" }}>
                    {t.hero.learnedPrior}
                  </span>
                  <span
                    style={{
                      fontSize: "8px",
                      fontFamily: "var(--font-mono)",
                      color: "#A78BFA",
                      background: "rgba(167, 139, 250, 0.15)",
                      padding: "1px 5px",
                      borderRadius: "4px",
                      fontWeight: 700,
                    }}
                  >
                    {t.hero.calibratedBadge}
                  </span>
                </div>
                <div
                  className="font-heading"
                  style={{ fontSize: "22px", fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em" }}
                >
                  12.8 <span style={{ fontSize: "12px", color: "#94A3B8", fontWeight: 500, fontFamily: "var(--font-mono)" }}>cm/d K_sat</span>
                </div>
                <div style={{ fontSize: "10px", color: "#A78BFA", marginTop: "2px" }}>
                  -19.4% Uncertainty Reduced
                </div>
              </div>
            </div>

            {/* Card 4: Cryptographic Merkle Provenance */}
            <div
              className="hover-lift transition-smooth"
              style={{
                padding: "18px 20px",
                display: "flex",
                alignItems: "center",
                gap: "14px",
                cursor: "default",
              }}
            >
              {/* Circular Radial Gauge */}
              <div style={{ position: "relative", width: "52px", height: "52px", flexShrink: 0 }}>
                <svg viewBox="0 0 36 36" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="3.5"
                  />
                  <path
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    stroke="#34D399"
                    strokeWidth="3.5"
                    strokeDasharray="100, 100"
                    strokeLinecap="round"
                    style={{
                      transition: "stroke-dasharray 1s ease",
                      filter: "drop-shadow(0 0 6px rgba(52, 211, 153, 0.5))",
                    }}
                  />
                </svg>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "11px",
                    fontWeight: 800,
                    fontFamily: "var(--font-mono)",
                    color: "#34D399",
                  }}
                >
                  100%
                </div>
              </div>

              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                  <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: "#94A3B8" }}>
                    {t.hero.dagLedger}
                  </span>
                  <span
                    style={{
                      fontSize: "8px",
                      fontFamily: "var(--font-mono)",
                      color: "#34D399",
                      background: "rgba(52, 211, 153, 0.15)",
                      padding: "1px 5px",
                      borderRadius: "4px",
                      fontWeight: 700,
                    }}
                  >
                    {t.hero.verifiedBadge}
                  </span>
                </div>
                <div
                  className="font-heading"
                  style={{ fontSize: "22px", fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em" }}
                >
                  0x9F28 <span style={{ fontSize: "12px", color: "#94A3B8", fontWeight: 500, fontFamily: "var(--font-mono)" }}>DAG Block</span>
                </div>
                <div style={{ fontSize: "10px", color: "#34D399", marginTop: "2px" }}>
                  {t.hero.sensorProof}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 960px) {
          .cockpit-main-grid {
            grid-template-columns: 1fr !important;
          }
          .cockpit-bento-grid {
            grid-template-columns: repeat(2, 1fr) !important;
          }
        }
        @media (max-width: 640px) {
          .cockpit-bento-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </section>
  );
}
