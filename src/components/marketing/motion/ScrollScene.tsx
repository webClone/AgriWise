"use client";
import { useRef, type ReactNode } from "react";
import {
  motion,
  useScroll,
  useTransform,
  useReducedMotion,
  type MotionValue,
} from "framer-motion";

/* ═══ ScrollScene ══════════════════════════════════════════════
   Wrapper for scroll-driven section animations.
   Uses framer-motion useScroll + useTransform.
   
   RESTRICTED TO ~5 scenes max per page to avoid performance issues:
   - Hero/scale transition
   - AgriBrain evidence transformation
   - ASMAE/trust
   - Worldline
   - Government zoom-out
   
   On reduced-motion, renders children statically.
   ═══════════════════════════════════════════════════════════════ */

interface ScrollSceneProps {
  children:
    | ReactNode
    | ((progress: MotionValue<number>) => ReactNode);
  /** Additional className for the container */
  className?: string;
  /** Height of the scrollable area relative to viewport (e.g., 2 = 200vh) */
  scrollHeight?: number;
  /** Whether the content should stick during scroll */
  sticky?: boolean;
}

export function ScrollScene({
  children,
  className = "",
  scrollHeight = 2,
  sticky = true,
}: ScrollSceneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const prefersReduced = useReducedMotion();

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // On reduced motion, render without scroll effects
  if (prefersReduced) {
    return (
      <div className={className}>
        {typeof children === "function"
          ? children(scrollYProgress)
          : children}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        position: "relative",
        height: `${scrollHeight * 100}vh`,
      }}
    >
      {sticky ? (
        <div
          style={{
            position: "sticky",
            top: 0,
            height: "100vh",
            overflow: "hidden",
          }}
        >
          {typeof children === "function"
            ? children(scrollYProgress)
            : children}
        </div>
      ) : (
        typeof children === "function"
          ? children(scrollYProgress)
          : children
      )}
    </div>
  );
}

/* ═══ ScrollFade ═══════════════════════════════════════════════
   Fades and optionally translates content based on scroll progress.
   Lighter-weight than ScrollScene for simple scroll effects.
   ═══════════════════════════════════════════════════════════════ */

interface ScrollFadeProps {
  children: ReactNode;
  className?: string;
  /** Scroll progress range where element is fully visible [start, end] */
  visibleRange?: [number, number];
  /** The MotionValue to track (from parent ScrollScene) */
  progress: MotionValue<number>;
  /** Y offset range in pixels */
  yRange?: [number, number];
}

export function ScrollFade({
  children,
  className = "",
  visibleRange = [0, 1],
  progress,
  yRange = [30, 0],
}: ScrollFadeProps) {
  const prefersReduced = useReducedMotion();

  const opacity = useTransform(
    progress,
    [
      Math.max(0, visibleRange[0] - 0.1),
      visibleRange[0],
      visibleRange[1],
      Math.min(1, visibleRange[1] + 0.1),
    ],
    [0, 1, 1, 0]
  );

  const y = useTransform(
    progress,
    [visibleRange[0] - 0.1, visibleRange[0]],
    prefersReduced ? [0, 0] : yRange
  );

  return (
    <motion.div
      className={className}
      style={prefersReduced ? {} : { opacity, y }}
    >
      {children}
    </motion.div>
  );
}
