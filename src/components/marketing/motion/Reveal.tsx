"use client";
import { useRef } from "react";
import {
  motion,
  useInView,
  useReducedMotion,
  type Variant,
} from "framer-motion";
import type { ReactNode } from "react";

/* ═══ Reveal ═══════════════════════════════════════════════════
   Framer-motion-powered reveal-on-scroll primitive.
   Replaces the legacy IntersectionObserver-based Reveal.
   Respects prefers-reduced-motion.
   ═══════════════════════════════════════════════════════════════ */

interface RevealProps {
  children: ReactNode;
  /** Delay in seconds before animation starts */
  delay?: number;
  /** Animation direction */
  direction?: "up" | "down" | "left" | "right" | "none";
  /** Distance in pixels for the slide */
  distance?: number;
  /** Additional className */
  className?: string;
  /** Whether to animate only once */
  once?: boolean;
  /** IntersectionObserver threshold (0-1) */
  threshold?: number;
  /** HTML element to render */
  as?: React.ElementType;
}

const directionOffsets: Record<
  NonNullable<RevealProps["direction"]>,
  { x: number; y: number }
> = {
  up: { x: 0, y: 24 },
  down: { x: 0, y: -24 },
  left: { x: 24, y: 0 },
  right: { x: -24, y: 0 },
  none: { x: 0, y: 0 },
};

export function Reveal({
  children,
  delay = 0,
  direction = "up",
  distance,
  className = "",
  once = true,
  threshold = 0.1,
}: RevealProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once, amount: threshold });
  const prefersReduced = useReducedMotion();

  const offset = directionOffsets[direction];
  const dist = distance ?? Math.abs(offset.x || offset.y);
  const scale = dist / Math.abs(offset.x || offset.y || 1);

  const hidden: Variant = prefersReduced
    ? { opacity: 0 }
    : {
        opacity: 0,
        x: offset.x * scale,
        y: offset.y * scale,
      };

  const visible: Variant = {
    opacity: 1,
    x: 0,
    y: 0,
  };

  return (
    <motion.div
      ref={ref}
      initial={hidden}
      animate={isInView ? visible : hidden}
      transition={{
        duration: prefersReduced ? 0 : 0.7,
        delay: prefersReduced ? 0 : delay,
        ease: [0.16, 1, 0.3, 1],
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ═══ StaggerContainer ═════════════════════════════════════════
   Parent container for staggered reveal of child items.
   ═══════════════════════════════════════════════════════════════ */

interface StaggerContainerProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  /** Delay between each child animation */
  stagger?: number;
  /** Initial delay before stagger begins */
  delay?: number;
  once?: boolean;
  threshold?: number;
}

export function StaggerContainer({
  children,
  className = "",
  style,
  stagger = 0.06,
  delay = 0,
  once = true,
  threshold = 0.1,
}: StaggerContainerProps) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once, amount: threshold });
  const prefersReduced = useReducedMotion();

  return (
    <motion.div
      ref={ref}
      style={style}
      initial="hidden"
      animate={isInView ? "visible" : "hidden"}
      variants={{
        hidden: {},
        visible: {
          transition: {
            staggerChildren: prefersReduced ? 0 : stagger,
            delayChildren: prefersReduced ? 0 : delay,
          },
        },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ═══ StaggerItem ══════════════════════════════════════════════
   Child item within a StaggerContainer.
   ═══════════════════════════════════════════════════════════════ */

interface StaggerItemProps {
  children: ReactNode;
  className?: string;
  direction?: "up" | "down" | "left" | "right" | "none";
}

export function StaggerItem({
  children,
  className = "",
  direction = "up",
}: StaggerItemProps) {
  const prefersReduced = useReducedMotion();
  const offset = directionOffsets[direction];

  return (
    <motion.div
      variants={{
        hidden: prefersReduced
          ? { opacity: 0 }
          : { opacity: 0, x: offset.x, y: offset.y },
        visible: {
          opacity: 1,
          x: 0,
          y: 0,
          transition: {
            duration: prefersReduced ? 0 : 0.6,
            ease: [0.16, 1, 0.3, 1],
          },
        },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
