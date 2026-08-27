"use client";

/* ═══ AgriWise R2 — PerformanceController ══════════════════════
   Persistent WebGL Stage Performance & Resource Manager.
   
   Handles:
   - Device Pixel Ratio (DPR) capping (max 2.0 desktop, 1.5 mobile)
   - Tab visibility suspension (pauses rendering when tab is backgrounded)
   - WebGL context loss recovery
   - Reduced-motion mode detection & static composition fallback
   - Layer offscreen pause
   ═══════════════════════════════════════════════════════════════ */

export interface PerformanceProfile {
  maxDpr: number;
  isMobile: boolean;
  prefersReducedMotion: boolean;
  isTabVisible: boolean;
  contextLost: boolean;
}

export class PerformanceController {
  private profile: PerformanceProfile = {
    maxDpr: 2.0,
    isMobile: false,
    prefersReducedMotion: false,
    isTabVisible: true,
    contextLost: false,
  };

  private listeners: Set<(profile: PerformanceProfile) => void> = new Set();

  constructor() {
    if (typeof window === "undefined") return;

    this.updateProfile();
    this.initListeners();
  }

  private updateProfile() {
    if (typeof window === "undefined") return;

    const isMobile = window.innerWidth <= 768 || /Mobi|Android/i.test(navigator.userAgent);
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const maxDpr = isMobile ? Math.min(window.devicePixelRatio, 1.5) : Math.min(window.devicePixelRatio, 2.0);
    const isTabVisible = !document.hidden;

    this.profile = {
      ...this.profile,
      maxDpr,
      isMobile,
      prefersReducedMotion,
      isTabVisible,
    };
  }

  private initListeners() {
    if (typeof window === "undefined") return;

    const handleVisibilityChange = () => {
      this.profile.isTabVisible = !document.hidden;
      this.notify();
    };

    const handleResize = () => {
      this.updateProfile();
      this.notify();
    };

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleMotionChange = (e: MediaQueryListEvent) => {
      this.profile.prefersReducedMotion = e.matches;
      this.notify();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("resize", handleResize);
    if (motionQuery.addEventListener) {
      motionQuery.addEventListener("change", handleMotionChange);
    }
  }

  public handleContextLoss() {
    this.profile.contextLost = true;
    this.notify();
  }

  public handleContextRestored() {
    this.profile.contextLost = false;
    this.notify();
  }

  public subscribe(callback: (profile: PerformanceProfile) => void) {
    this.listeners.add(callback);
    callback(this.profile);
    return () => {
      this.listeners.delete(callback);
    };
  }

  private notify() {
    this.listeners.forEach((cb) => cb(this.profile));
  }

  public getProfile(): PerformanceProfile {
    return this.profile;
  }
}

export const globalPerformanceController = new PerformanceController();
