"use client";

import { useEffect, useRef, useState } from "react";

/** Tiny canvas particle field — ambient floating dots */
export default function ParticleField({ color = "#4ade80", count = 35 }: { color?: string; count?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;

    let raf: number;
    const particles: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = [];
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; };
    resize();
    window.addEventListener("resize", resize);

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * c.width, y: Math.random() * c.height,
        vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.2,
        r: Math.random() * 1.5 + 0.5, a: Math.random() * 0.3 + 0.05,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      for (const p of particles) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = c.width; if (p.x > c.width) p.x = 0;
        if (p.y < 0) p.y = c.height; if (p.y > c.height) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = p.a;
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, [color, count]);

  return <canvas ref={ref} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 0 }} />;
}

/** Animated ring chart */
export function RingChart({ value, size = 56, stroke = 4, color = "#4ade80", bg = "rgba(71,85,105,0.15)", label }: {
  value: number; size?: number; stroke?: number; color?: string; bg?: string; label?: string;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { const t = setTimeout(() => setMounted(true), 300); return () => clearTimeout(t); }, []);

  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, value));
  const offset = circ - (circ * (mounted ? pct : 0)) / 100;

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }} suppressHydrationWarning={true}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={bg} strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }} suppressHydrationWarning={true}>
        <span style={{ fontSize: size < 50 ? "11px" : "14px", fontWeight: 800, color: "#f1f5f9", lineHeight: 1 }}>{pct}%</span>
        {label && <span style={{ fontSize: "7px", color: "#475569", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>}
      </div>
    </div>
  );
}

/** Animated counter */
export function AnimatedNumber({ value, duration = 1200, suffix = "", color = "#f1f5f9", size = "1.6rem" }: {
  value: number; duration?: number; suffix?: string; color?: string; size?: string;
}) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start: number | null = null;
    const step = (ts: number) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(value * ease * 10) / 10);
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [value, duration]);

  const isInt = Number.isInteger(value);
  return <span style={{ fontSize: size, fontWeight: 800, color, lineHeight: 1, fontFamily: "'Inter', monospace" }}>{isInt ? Math.round(display) : display.toFixed(1)}{suffix}</span>;
}
