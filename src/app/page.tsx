"use client";
import Link from "next/link";
import HeroSection from "@/components/landing/HeroSection";
import FeaturesSection from "@/components/landing/FeaturesSection";
import DataSection from "@/components/landing/DataSection";
import ScienceSection from "@/components/landing/ScienceSection";
import BottomSections from "@/components/landing/BottomSections";
import { ThemeProvider, ThemeToggle, useTheme } from "@/components/landing/ThemeProvider";
import { ThemeLogo } from "@/components/landing/ThemeLogo";
import "@/components/landing/agribrain-theme.css";

function HomeContent() {
  const { theme } = useTheme();
  return (
    <div data-theme={theme} style={{ minHeight: "100vh", background: "#050a14", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif", overflowX: "hidden" }}>
      {/* ═══ NAVBAR ════════════════════════════════════════════ */}
      <nav style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, padding: "14px 24px", background: "rgba(5,10,20,0.82)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", borderBottom: "1px solid rgba(71,85,105,0.06)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Link href="/" style={{ textDecoration: "none" }}>
            <ThemeLogo height={80} />
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
            <Link href="#perception" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none", fontWeight: 500, transition: "color 0.15s" }}>Perception</Link>
            <Link href="#features" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none", fontWeight: 500, transition: "color 0.15s" }}>Features</Link>
            <Link href="#data" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none", fontWeight: 500, transition: "color 0.15s" }}>Data</Link>
            <Link href="#science" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none", fontWeight: 500, transition: "color 0.15s" }}>Science</Link>
            <Link href="/agribrain" style={{ fontSize: "13px", color: "#818cf8", textDecoration: "none", fontWeight: 600, transition: "color 0.15s" }}>🧠 AgriBrain</Link>
            <Link href="#how" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none", fontWeight: 500, transition: "color 0.15s" }}>How It Works</Link>
            <ThemeToggle />
            <Link href="/farm" className="hp-cta-nav" style={{ padding: "8px 20px", borderRadius: "10px", background: "linear-gradient(135deg,#22c55e,#16a34a)", color: "#fff", fontSize: "13px", fontWeight: 700, textDecoration: "none", boxShadow: "0 2px 12px rgba(34,197,94,0.2)" }}>Launch App</Link>
          </div>
        </div>
      </nav>

      <HeroSection />
      <FeaturesSection />
      <DataSection />
      <ScienceSection />
      <BottomSections />

      {/* ═══ GLOBAL STYLES ════════════════════════════════════ */}
      <style>{`
        @keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }
        @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(1.5)} }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes tickSlide { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes marquee { from{transform:translateX(0)} to{transform:translateX(-50%)} }
        @keyframes fadeSlideUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
        .hp-grad-text {
          background: linear-gradient(135deg, #4ade80 0%, #22d3ee 40%, #818cf8 100%);
          -webkit-background-clip: text; -webkit-text-fill-color: transparent;
          background-size: 200% 200%; animation: hpGrad 6s ease infinite;
        }
        @keyframes hpGrad { 0%,100%{background-position:0% 50%} 50%{background-position:100% 50%} }
        .hp-shimmer {
          position:absolute; top:0; left:-100%; width:100%; height:100%;
          background:linear-gradient(90deg,transparent,rgba(255,255,255,0.12),transparent);
          animation: hpShim 3s ease-in-out infinite;
        }
        @keyframes hpShim { 0%{left:-100%} 35%,100%{left:100%} }
        .hp-cta { transition: all 0.2s cubic-bezier(0.16,1,0.3,1); position:relative; overflow:hidden; }
        .hp-cta:hover { transform:translateY(-3px) scale(1.02); box-shadow:0 10px 40px rgba(34,197,94,0.4) !important; }
        .hp-cta:active { transform:translateY(0) scale(0.97); }
        .hp-cta-ghost { transition: all 0.2s ease; }
        .hp-cta-ghost:hover { background:rgba(71,85,105,0.15) !important; color:#e2e8f0 !important; transform:translateY(-2px); }
        .hp-cta-nav { transition: all 0.15s ease; }
        .hp-cta-nav:hover { transform:translateY(-1px); box-shadow:0 4px 16px rgba(34,197,94,0.3) !important; }
        .hp-fcard { transition: all 0.25s cubic-bezier(0.16,1,0.3,1); }
        .hp-fcard:hover { border-color:rgba(100,116,139,0.18) !important; transform:translateY(-4px); box-shadow:0 14px 50px rgba(0,0,0,0.3); }
        .hp-float { animation: hpFloat 4s ease-in-out infinite; }
        @keyframes hpFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
        .hp-src-badge { transition: all 0.2s ease; }
        .hp-src-badge:hover { transform:translateY(-2px); border-color:rgba(100,116,139,0.2) !important; }
        @media (max-width: 900px) {
          nav [style*="gap: 20px"] { gap: 8px !important; }
          section [style*="grid-template-columns: repeat(4"] { grid-template-columns: repeat(2,1fr) !important; }
          section [style*="grid-template-columns: 1fr 1fr 1fr"] { grid-template-columns: 1fr !important; }
          section [style*="grid-template-columns: 1fr 1fr"] { grid-template-columns: 1fr !important; }
          section [style*="grid-template-columns: repeat(3"] { grid-template-columns: 1fr !important; }
          section [style*="grid-template-columns: repeat(6"] { grid-template-columns: repeat(3,1fr) !important; }
          section [style*="grid-template-columns: 2fr"] { grid-template-columns: 1fr !important; }
          section [style*="grid-template-columns: 180px"] { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

export default function Home() {
  return (
    <ThemeProvider>
      <HomeContent />
    </ThemeProvider>
  );
}
