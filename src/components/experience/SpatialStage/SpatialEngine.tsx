"use client";

import React, { useEffect, useRef, useState } from "react";
import { Deck } from "@deck.gl/core";
import { ScrollEngine } from "./ScrollEngine";
import { solvePageSpaceRenderState } from "./TimelineCompiler";
import type { ResolvedShotState, SpatialStage } from "./ShotDirector";
import { buildActiveLayers } from "./LayerRegistry";
import { globalPerformanceController } from "./PerformanceController";
import { emitMarketingEvent } from "../analytics/MarketingTelemetry";
import ChapterScrollNav from "./ChapterScrollNav";

/* ═══ AgriWise R2 Pass 5 — SpatialEngine ═════════════════════════
   Cinematic Spatial Engine Island with Inertial Visual Smoother
   and Interactive Chapter Navigation Dock.
   ═══════════════════════════════════════════════════════════════ */

export default function SpatialEngine() {
  const containerRef = useRef<HTMLDivElement>(null);
  const deckRef = useRef<Deck | null>(null);
  const scrollEngineRef = useRef<ScrollEngine | null>(null);
  const rafRef = useRef<number | null>(null);
  const isDirtyRef = useRef<boolean>(true);
  const isRunningRef = useRef<boolean>(false);
  const webglReadyEmittedRef = useRef<boolean>(false);

  // Inertial Smoother State
  const renderedScrollYRef = useRef<number>(0);
  const targetScrollYRef = useRef<number>(0);
  const lastTimeRef = useRef<number>(0);

  // State trackers
  const [currentStage, setCurrentStage] = useState<SpatialStage>("field");
  const lastSettledStageRef = useRef<string>("");
  const prefersReducedRef = useRef<boolean>(false);
  const frameOverrideRef = useRef<string | null>(null);
  const transitionOverrideRef = useRef<{ name: string; t: number } | null>(null);
  const [debugState, setDebugState] = useState<ResolvedShotState | null>(null);

  useEffect(() => {
    if (!containerRef.current || typeof window === "undefined") return;

    // 1. Check test parameters (?r2SpatialOnly, ?r2Frame, ?r2Transition, ?r2Debug)
    const params = new URLSearchParams(window.location.search);
    if (params.get("r2SpatialOnly") === "1") {
      document.querySelectorAll<HTMLElement>("[data-r2-narrative]").forEach((el) => {
        el.style.visibility = "hidden";
      });
    }

    frameOverrideRef.current = params.get("r2Frame");

    const transName = params.get("r2Transition");
    const transT = params.get("t");
    if (transName) {
      transitionOverrideRef.current = {
        name: transName,
        t: transT ? parseFloat(transT) : 0.5,
      };
    }

    // 2. Check reduced motion
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    prefersReducedRef.current = mql.matches;

    const perf = globalPerformanceController.getProfile();

    // 3. Create imperative Deck instance
    const deck = new Deck({
      parent: containerRef.current,
      viewState: {
        longitude: 3.016,
        latitude: 36.5025,
        zoom: 16.0,
        pitch: 42,
        bearing: -15,
      },
      layers: [],
      controller: false,
      useDevicePixels: perf.maxDpr,
      style: { position: "absolute", top: "0", left: "0", width: "100%", height: "100%" },
      getCursor: () => "default",
      onAfterRender: () => {
        if (!webglReadyEmittedRef.current && typeof window !== "undefined") {
          webglReadyEmittedRef.current = true;
          window.dispatchEvent(new CustomEvent("agriwise_webgl_ready"));
        }
      },
    });
    deckRef.current = deck;

    // 4. Start ScrollEngine
    const scrollEngine = new ScrollEngine();
    scrollEngine.start();
    scrollEngineRef.current = scrollEngine;

    emitMarketingEvent("hero_view");

    // Initialize smoother position
    const initialScrollY = window.scrollY || window.pageYOffset || 0;
    renderedScrollYRef.current = initialScrollY;
    targetScrollYRef.current = initialScrollY;
    lastTimeRef.current = performance.now();

    // 5. Inertial Smoothed Render Loop
    function markDirty() {
      isDirtyRef.current = true;
      if (!isRunningRef.current) {
        isRunningRef.current = true;
        lastTimeRef.current = performance.now();
        rafRef.current = requestAnimationFrame(renderLoop);
      }
    }

    function renderLoop(now: number) {
      if (!deckRef.current || !scrollEngineRef.current) {
        isRunningRef.current = false;
        return;
      }

      const dt = Math.min((now - lastTimeRef.current) / 1000, 0.05);
      lastTimeRef.current = now;

      // Update target scroll from window
      targetScrollYRef.current = window.scrollY || window.pageYOffset || 0;

      // Check if test override or reduced motion (skip inertia)
      const skipInertia =
        prefersReducedRef.current ||
        frameOverrideRef.current !== null ||
        transitionOverrideRef.current !== null;

      if (skipInertia) {
        renderedScrollYRef.current = targetScrollYRef.current;
      } else {
        // Critically damped visual smoothing (~120ms tau)
        const diff = targetScrollYRef.current - renderedScrollYRef.current;
        if (Math.abs(diff) < 0.2) {
          renderedScrollYRef.current = targetScrollYRef.current;
        } else {
          // Exponential decay: rendered += diff * (1 - e^(-dt / tau))
          const factor = 1 - Math.exp(-dt / 0.12);
          renderedScrollYRef.current += diff * factor;
          isDirtyRef.current = true; // Continue smoothing
        }
      }

      // Build simulated snapshot with smoothed scrollY
      const rawSnapshot = scrollEngineRef.current.getSnapshot();
      const smoothedSnapshot = {
        ...rawSnapshot,
        scrollY: renderedScrollYRef.current,
      };

      // Solve Page-Space Render State via TimelineCompiler & ShotDirector
      const state = solvePageSpaceRenderState(
        smoothedSnapshot,
        prefersReducedRef.current,
        frameOverrideRef.current,
        transitionOverrideRef.current
      );

      // Imperative Deck.gl Update
      const layers = buildActiveLayers(state);
      deckRef.current.setProps({
        viewState: state.camera,
        layers,
      });

      // Sync active stage for Chapter Navigation Pill
      if (state.stage && state.stage !== currentStage) {
        setCurrentStage(state.stage);
      }

      // Telemetry: Emitted ONLY when settled stage changes
      if (state.settledStage && state.settledStage !== lastSettledStageRef.current) {
        lastSettledStageRef.current = state.settledStage;
        if (state.settledStage === "field") emitMarketingEvent("scale_field_reached");
        else if (state.settledStage === "farm") emitMarketingEvent("scale_farm_reached");
        else if (state.settledStage === "organization") emitMarketingEvent("scale_organization_reached");
        else if (state.settledStage === "region") emitMarketingEvent("scale_region_reached");
        else if (state.settledStage === "nation") emitMarketingEvent("scale_nation_reached");
      }

      // Dev Debug State (?r2Debug=1)
      if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("r2Debug") === "1") {
        setDebugState({ ...state });
      }

      // Check if another frame is needed
      const hasMotionRemaining = Math.abs(targetScrollYRef.current - renderedScrollYRef.current) > 0.2;

      if (hasMotionRemaining || isDirtyRef.current) {
        isDirtyRef.current = false;
        rafRef.current = requestAnimationFrame(renderLoop);
      } else {
        // Sleep RAF loop until next scroll or window event
        isRunningRef.current = false;
        rafRef.current = null;
      }
    }

    // Wake render loop on motion changes, scroll & resize
    const handleMotionChange = (e: MediaQueryListEvent) => {
      prefersReducedRef.current = e.matches;
      markDirty();
    };
    mql.addEventListener("change", handleMotionChange);

    const handleScrollOrResize = () => markDirty();
    window.addEventListener("scroll", handleScrollOrResize, { passive: true });
    window.addEventListener("resize", handleScrollOrResize);

    // Initial render
    markDirty();

    // Subscribe to PerformanceController
    const unsubscribePerf = globalPerformanceController.subscribe((profile) => {
      if (deckRef.current) {
        deckRef.current.setProps({ useDevicePixels: profile.maxDpr });
        markDirty();
      }
    });

    return () => {
      mql.removeEventListener("change", handleMotionChange);
      window.removeEventListener("scroll", handleScrollOrResize);
      window.removeEventListener("resize", handleScrollOrResize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      unsubscribePerf();
      scrollEngineRef.current?.dispose();
      deckRef.current?.finalize();
      deckRef.current = null;
      scrollEngineRef.current = null;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="r2-spatial-engine-island"
      data-r2-cinematic="true"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
        pointerEvents: "none",
        overflow: "hidden",
      }}
    >
      {/* Interactive Chapter Scroll Navigation Dock */}
      <div style={{ pointerEvents: "auto" }}>
        <ChapterScrollNav currentStage={currentStage} />
      </div>

      {/* Discreet Quiet Micro-Watermark (Clean Cinematic presentation, No Card Box) */}
      <div
        style={{
          position: "fixed",
          bottom: "16px",
          right: "20px",
          zIndex: 40,
          color: "rgba(148, 163, 184, 0.45)",
          fontSize: "10px",
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.12em",
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        ILLUSTRATIVE SPATIAL DEMONSTRATION
      </div>

      {/* Dev Debug Overlay (Only visible with ?r2Debug=1) */}
      {debugState && (
        <div
          style={{
            position: "fixed",
            top: "70px",
            left: "16px",
            zIndex: 9999,
            background: "rgba(0, 0, 0, 0.88)",
            border: "1px solid rgba(74, 222, 128, 0.4)",
            borderRadius: "8px",
            padding: "10px 14px",
            color: "#4ade80",
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            lineHeight: 1.4,
            pointerEvents: "auto",
            maxWidth: "360px",
          }}
        >
          <div style={{ fontWeight: 800, color: "#fff", marginBottom: "4px" }}>
            AgriWise Cinematic Shot HUD
          </div>
          <div>Stage: {debugState.stage} (settled: {String(debugState.settledStage)})</div>
          <div>Transition: {debugState.fromStage} → {debugState.toStage} (t: {debugState.transitionT.toFixed(2)})</div>
          <div>Zoom: {debugState.camera.zoom.toFixed(2)} | Pitch: {debugState.camera.pitch.toFixed(1)}°</div>
          <div>Channels: opt:{debugState.channels.opticalField.toFixed(2)} env:{debugState.channels.microMotion.farmEnvelope.drawProgress.toFixed(2)}</div>
        </div>
      )}
    </div>
  );
}
