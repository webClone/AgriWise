"use client";

import React, { useEffect } from "react";
import type { SpatialStage } from "./ShotDirector";

/* ═══ AgriWise ChapterScrollNav ═════════════════════════════════
   Interactive Glassmorphic Chapter Navigation Dock.
   
   Features:
   - 5 Spatial Scale milestones: FIELD · FARM · ORG · REGION · NATION
   - Real-time active pill indicator
   - Click to glide smoothly to any scale scene
   - Up/Down arrow key navigation to roll through sections
   ═══════════════════════════════════════════════════════════════ */

interface ChapterScrollNavProps {
  currentStage: SpatialStage;
}

const CHAPTERS: { id: SpatialStage; num: string; label: string; elementId: string }[] = [
  { id: "field", num: "01", label: "FIELD", elementId: "shot-field" },
  { id: "farm", num: "02", label: "FARM", elementId: "shot-farm" },
  { id: "organization", num: "03", label: "ORG", elementId: "shot-organization" },
  { id: "region", num: "04", label: "REGION", elementId: "shot-region" },
  { id: "nation", num: "05", label: "NATION", elementId: "shot-nation" },
];

export default function ChapterScrollNav({ currentStage }: ChapterScrollNavProps) {
  const [isDebug, setIsDebug] = React.useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setIsDebug(params.get("r2Debug") === "1" || params.get("r2Nav") === "1");
  }, []);

  useEffect(() => {
    if (!isDebug) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (["INPUT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName)) return;

      const currentIndex = CHAPTERS.findIndex((c) => c.id === currentStage);
      if (currentIndex === -1) return;

      if (e.key === "ArrowDown" || e.key === "PageDown") {
        if (currentIndex < CHAPTERS.length - 1) {
          e.preventDefault();
          scrollToChapter(CHAPTERS[currentIndex + 1].id);
        }
      } else if (e.key === "ArrowUp" || e.key === "PageUp") {
        if (currentIndex > 0) {
          e.preventDefault();
          scrollToChapter(CHAPTERS[currentIndex - 1].id);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentStage]);

  const scrollToChapter = (stageId: SpatialStage) => {
    if (stageId === "field") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    const target = CHAPTERS.find((c) => c.id === stageId);
    if (!target) return;

    const el = document.getElementById(target.elementId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  if (!isDebug) return null;

  return (
    <nav
      aria-label="Spatial Chapter Navigation"
      style={{
        position: "fixed",
        bottom: "32px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        gap: "4px",
        background: "rgba(5, 10, 20, 0.88)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: "1px solid rgba(74, 222, 128, 0.3)",
        borderRadius: "9999px",
        padding: "5px 8px",
        boxShadow: "0 12px 40px 0 rgba(0, 0, 0, 0.6), 0 0 16px rgba(74, 222, 128, 0.15)",
        transition: "opacity 300ms ease",
        pointerEvents: "auto",
      }}
    >
      {CHAPTERS.map((ch) => {
        const isActive = currentStage === ch.id;
        return (
          <button
            key={ch.id}
            type="button"
            onClick={() => scrollToChapter(ch.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 16px",
              borderRadius: "9999px",
              background: isActive ? "rgba(74, 222, 128, 0.22)" : "transparent",
              border: isActive ? "1px solid rgba(74, 222, 128, 0.6)" : "1px solid transparent",
              color: isActive ? "#4ade80" : "rgba(148, 163, 184, 0.8)",
              fontFamily: "var(--font-mono, monospace)",
              fontSize: "11px",
              fontWeight: isActive ? 700 : 500,
              letterSpacing: "0.08em",
              cursor: "pointer",
              transition: "all 200ms cubic-bezier(0.4, 0, 0.2, 1)",
              outline: "none",
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.color = "#ffffff";
                e.currentTarget.style.background = "rgba(255, 255, 255, 0.08)";
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.color = "rgba(148, 163, 184, 0.8)";
                e.currentTarget.style.background = "transparent";
              }
            }}
          >
            <span style={{ opacity: 0.6, fontSize: "9px" }}>{ch.num}</span>
            <span>{ch.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
