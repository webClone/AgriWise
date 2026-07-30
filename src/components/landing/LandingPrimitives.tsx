"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";

/* ── Canvas Particles ────────────────────────────────────── */
export function Particles({ color = "rgba(74,222,128,0.3)", n = 40 }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d"); if (!ctx) return;
    let raf: number;
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; };
    resize(); window.addEventListener("resize", resize);
    const dots = Array.from({ length: n }, () => ({
      x: Math.random() * c.width, y: Math.random() * c.height,
      vx: (Math.random() - 0.5) * 0.2, vy: (Math.random() - 0.5) * 0.12,
      r: Math.random() * 1.5 + 0.4, a: Math.random() * 0.2 + 0.04,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      for (const p of dots) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = c.width; if (p.x > c.width) p.x = 0;
        if (p.y < 0) p.y = c.height; if (p.y > c.height) p.y = 0;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = color; ctx.globalAlpha = p.a; ctx.fill();
      }
      ctx.globalAlpha = 1; raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, [color, n]);
  return <canvas ref={ref} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }} />;
}

/* ── Intersection-driven reveal ──────────────────────────── */
export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [v, setV] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setV(true); obs.disconnect(); } }, { threshold: 0.1 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return <div ref={ref} className={className} style={{ opacity: v ? 1 : 0, transform: v ? "translateY(0)" : "translateY(28px)", transition: `all 0.7s cubic-bezier(0.16,1,0.3,1) ${delay}s` }}>{children}</div>;
}

/* ── Animated counter ────────────────────────────────────── */
export function Counter({ end, suffix = "", prefix = "" }: { end: number; suffix?: string; prefix?: string }) {
  const [v, setV] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        let start: number | null = null;
        const step = (ts: number) => {
          if (!start) start = ts;
          const p = Math.min((ts - start) / 1800, 1);
          setV(Math.round(end * (1 - Math.pow(1 - p, 3))));
          if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step); obs.disconnect();
      }
    }, { threshold: 0.3 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [end]);
  return <span ref={ref}>{prefix}{v.toLocaleString()}{suffix}</span>;
}

/* ── Typing animation ────────────────────────────────────── */
export function TypeWriter({ texts, speed = 60, pause = 2500 }: { texts: string[]; speed?: number; pause?: number }) {
  const [idx, setIdx] = useState(0);
  const [chars, setChars] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const word = texts[idx];
    if (!deleting && chars < word.length) {
      const t = setTimeout(() => setChars(c => c + 1), speed);
      return () => clearTimeout(t);
    } else if (!deleting && chars === word.length) {
      const t = setTimeout(() => setDeleting(true), pause);
      return () => clearTimeout(t);
    } else if (deleting && chars > 0) {
      const t = setTimeout(() => setChars(c => c - 1), speed / 2);
      return () => clearTimeout(t);
    } else if (deleting && chars === 0) {
      setDeleting(false);
      setIdx(i => (i + 1) % texts.length);
    }
  }, [chars, deleting, idx, texts, speed, pause]);

  return (
    <span>
      {texts[idx].substring(0, chars)}
      <span style={{ borderRight: "2px solid #4ade80", marginLeft: "2px", animation: "blink 1s step-end infinite" }}>&nbsp;</span>
    </span>
  );
}

/* ── Orbit ring animation ────────────────────────────────── */
export function OrbitRing({ size = 300, dotCount = 8, color = "#4ade80", duration = 20 }: { size?: number; dotCount?: number; color?: string; duration?: number }) {
  return (
    <div style={{ width: size, height: size, position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, border: `1px solid ${color}10`, borderRadius: "50%", animation: `spin ${duration}s linear infinite` }}>
        {Array.from({ length: dotCount }).map((_, i) => (
          <div key={i} style={{
            position: "absolute", width: "4px", height: "4px", borderRadius: "50%",
            background: color, opacity: 0.3 + (i / dotCount) * 0.4,
            top: `${50 - 50 * Math.cos((2 * Math.PI * i) / dotCount)}%`,
            left: `${50 + 50 * Math.sin((2 * Math.PI * i) / dotCount)}%`,
            transform: "translate(-50%, -50%)",
          }} />
        ))}
      </div>
      <div style={{ position: "absolute", inset: "15%", border: `1px solid ${color}08`, borderRadius: "50%", animation: `spin ${duration * 0.7}s linear infinite reverse` }}>
        {Array.from({ length: Math.floor(dotCount / 2) }).map((_, i) => (
          <div key={i} style={{
            position: "absolute", width: "3px", height: "3px", borderRadius: "50%",
            background: color, opacity: 0.2,
            top: `${50 - 50 * Math.cos((2 * Math.PI * i) / (dotCount / 2))}%`,
            left: `${50 + 50 * Math.sin((2 * Math.PI * i) / (dotCount / 2))}%`,
            transform: "translate(-50%, -50%)",
          }} />
        ))}
      </div>
    </div>
  );
}

/* ── SVG Sparkline with draw animation ───────────────────── */
export function Sparkline({ data, width = 120, height = 32, color = "#4ade80", strokeW = 1.5 }: {
  data: number[]; width?: number; height?: number; color?: string; strokeW?: number;
}) {
  const ref = useRef<SVGPathElement>(null);
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setDrawn(true); obs.disconnect(); } }, { threshold: 0.3 });
    const el = ref.current?.closest("svg");
    if (el) obs.observe(el);
    return () => obs.disconnect();
  }, []);
  if (!data.length) return null;
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / range) * height * 0.8 - height * 0.1}`);
  const d = `M${pts.join("L")}`;
  const len = width * 2;
  return (
    <svg width={width} height={height} style={{ overflow: "visible" }}>
      <defs><linearGradient id={`sg${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity="0.3"/><stop offset="100%" stopColor={color} stopOpacity="0"/></linearGradient></defs>
      <path d={`${d}L${width},${height}L0,${height}Z`} fill={`url(#sg${color.replace("#","")})`} opacity={drawn ? 0.4 : 0} style={{ transition: "opacity 1s ease 0.5s" }}/>
      <path ref={ref} d={d} fill="none" stroke={color} strokeWidth={strokeW} strokeLinecap="round"
        strokeDasharray={len} strokeDashoffset={drawn ? 0 : len}
        style={{ transition: "stroke-dashoffset 1.5s cubic-bezier(0.16,1,0.3,1)" }} />
    </svg>
  );
}

/* ── Animated progress bar ───────────────────────────────── */
export function AnimBar({ value, color = "#4ade80", height = 4, label, suffix = "%" }: {
  value: number; color?: string; height?: number; label?: string; suffix?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setW(value); obs.disconnect(); } }, { threshold: 0.3 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [value]);
  return (
    <div ref={ref}>
      {label && <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
        <span style={{ fontSize: "10px", color: "#64748b", fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: "10px", color, fontWeight: 700, fontFamily: "monospace" }}>{Math.round(w)}{suffix}</span>
      </div>}
      <div style={{ height, borderRadius: height, background: "rgba(71,85,105,0.12)", overflow: "hidden" }}>
        <div style={{ height: "100%", borderRadius: height, width: `${w}%`, background: `linear-gradient(90deg, ${color}cc, ${color})`, transition: "width 1.4s cubic-bezier(0.16,1,0.3,1)", boxShadow: `0 0 8px ${color}30` }} />
      </div>
    </div>
  );
}

/* ── Live cycling ticker ─────────────────────────────────── */
export function LiveTicker({ items, interval = 3000 }: {
  items: { label: string; value: string; color: string; icon: string }[]; interval?: number;
}) {
  const [idx, setIdx] = useState(0);
  useEffect(() => { const t = setInterval(() => setIdx(i => (i + 1) % items.length), interval); return () => clearInterval(t); }, [items.length, interval]);
  const item = items[idx];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 16px", borderRadius: "10px", background: "rgba(15,23,42,0.6)", border: "1px solid rgba(71,85,105,0.08)", minWidth: "200px" }}>
      <span style={{ fontSize: "1.1rem" }}>{item.icon}</span>
      <div style={{ flex: 1, overflow: "hidden" }}>
        <div key={idx} style={{ animation: "tickSlide 0.4s ease", fontSize: "13px", fontWeight: 700, color: item.color }}>{item.value}</div>
        <div style={{ fontSize: "9px", color: "#475569", textTransform: "uppercase", letterSpacing: "0.06em" }}>{item.label}</div>
      </div>
      <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: item.color, boxShadow: `0 0 6px ${item.color}60`, animation: "pulse 2s ease-in-out infinite" }} />
    </div>
  );
}

/* ── Scrolling marquee ───────────────────────────────────── */
export function Marquee({ children, speed = 30 }: { children: ReactNode; speed?: number }) {
  return (
    <div style={{ overflow: "hidden", position: "relative" }}>
      <div style={{ display: "flex", width: "max-content", animation: `marquee ${speed}s linear infinite` }}>
        {children}{children}
      </div>
    </div>
  );
}

