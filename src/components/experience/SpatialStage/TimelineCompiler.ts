import type { ScrollSnapshot } from "./ScrollEngine";
import {
  directShot,
  type ResolvedShotState,
  type SpatialStage,
  type TimelinePosition,
  type VisualChannelProfile,
} from "./ShotDirector";

/* ═══ AgriWise R2 Pass 4 — TimelineCompiler ═════════════════════
   Compiles DOM scroll position into canonical TimelinePosition,
   then delegates to ShotDirector for cinematic choreography.
   
   Supports deterministic test URL parameters:
   - ?r2Frame=field|farm|organization|region|nation
   - ?r2Transition=field-farm&t=0.50
   - ?r2Transition=farm-organization&t=0.25
   - ?r2Transition=organization-region&t=0.75
   - ?r2Transition=region-nation&t=0.50
   - ?r2Transition=nation-evidence&t=0.50
   ═══════════════════════════════════════════════════════════════ */

export const SCALE_PACING = {
  fieldHold: 0.16,
  fieldToFarm: 0.12,
  farmHold: 0.14,
  farmToOrganization: 0.12,
  organizationHold: 0.14,
  organizationToRegion: 0.12,
  regionHold: 0.12,
  regionToNation: 0.14,
  nationHold: 0.28,
};

const TOTAL_PACING_WEIGHT = Object.values(SCALE_PACING).reduce((a, b) => a + b, 0);

interface CompiledSegment {
  type: "HOLD" | "TRANSITION";
  fromStage: SpatialStage;
  toStage: SpatialStage;
  startProgress: number;
  endProgress: number;
}

function compilePacingSegments(): CompiledSegment[] {
  const keys: (keyof typeof SCALE_PACING)[] = [
    "fieldHold",
    "fieldToFarm",
    "farmHold",
    "farmToOrganization",
    "organizationHold",
    "organizationToRegion",
    "regionHold",
    "regionToNation",
    "nationHold",
  ];

  let current = 0;
  return keys.map((key) => {
    const weight = SCALE_PACING[key] / TOTAL_PACING_WEIGHT;
    const startProgress = current;
    const endProgress = current + weight;
    current = endProgress;

    const isHold = key.includes("Hold");
    let fromStage: SpatialStage = "field";
    let toStage: SpatialStage = "field";

    if (key.startsWith("field")) {
      fromStage = "field";
      toStage = key === "fieldToFarm" ? "farm" : "field";
    } else if (key.startsWith("farm")) {
      fromStage = "farm";
      toStage = key === "farmToOrganization" ? "organization" : "farm";
    } else if (key.startsWith("organization")) {
      fromStage = "organization";
      toStage = key === "organizationToRegion" ? "region" : "organization";
    } else if (key.startsWith("region")) {
      fromStage = "region";
      toStage = key === "regionToNation" ? "nation" : "region";
    } else {
      fromStage = "nation";
      toStage = "nation";
    }

    return {
      type: isHold ? "HOLD" : "TRANSITION",
      fromStage,
      toStage,
      startProgress,
      endProgress,
    };
  });
}

const COMPILED_SEGMENTS = compilePacingSegments();

export function compileTimelinePosition(
  snapshot: ScrollSnapshot,
  transitionOverride: { name: string; t: number } | null = null,
  frameOverride: string | null = null
): TimelinePosition {
  // 1. Deterministic Frame Override (?r2Frame=field|farm|organization|region|nation)
  if (frameOverride && ["field", "farm", "organization", "region", "nation"].includes(frameOverride)) {
    return { type: "hold", stage: frameOverride as SpatialStage };
  }

  // 2. Deterministic Transition Override (?r2Transition=field-farm&t=0.5)
  if (transitionOverride) {
    const { name, t } = transitionOverride;
    const clampedT = Math.max(0, Math.min(1, t));

    if (name === "field-farm" || name === "field_farm") {
      return { type: "transition", from: "field", to: "farm", t: clampedT };
    }
    if (name === "farm-organization" || name === "farm_organization") {
      return { type: "transition", from: "farm", to: "organization", t: clampedT };
    }
    if (name === "organization-region" || name === "organization_region") {
      return { type: "transition", from: "organization", to: "region", t: clampedT };
    }
    if (name === "region-nation" || name === "region_nation") {
      return { type: "transition", from: "region", to: "nation", t: clampedT };
    }
    if (name === "nation-evidence" || name === "nation_evidence") {
      return { type: "evidence_dive", t: clampedT };
    }
  }

  const { scrollY, scaleTop, scaleBottom, evidenceBottom, viewportHeight } = snapshot;
  const vh = viewportHeight;

  // ── ZONE 1: HERO SPACE (scrollY < scaleTop) ────────────────
  if (scrollY < scaleTop - 50) {
    return { type: "hold", stage: "field" };
  }

  // ── ZONE 2: SCALE SPACE (scaleTop <= scrollY < scaleBottom - vh) ───
  if (scrollY <= scaleBottom - vh) {
    const scaleTrackLength = Math.max(100, scaleBottom - vh - scaleTop);
    const rawScaleP = (scrollY - scaleTop) / scaleTrackLength;
    const scaleP = Math.max(0, Math.min(1, rawScaleP));

    for (const seg of COMPILED_SEGMENTS) {
      if (scaleP >= seg.startProgress && scaleP <= seg.endProgress) {
        if (seg.type === "HOLD") {
          return { type: "hold", stage: seg.fromStage };
        } else {
          const segLen = Math.max(0.0001, seg.endProgress - seg.startProgress);
          const t = Math.max(0, Math.min(1, (scaleP - seg.startProgress) / segLen));
          return { type: "transition", from: seg.fromStage, to: seg.toStage, t };
        }
      }
    }

    return { type: "hold", stage: "nation" };
  }

  // ── ZONE 3: EVIDENCE DIVE (scaleBottom - vh < scrollY <= evidenceBottom - vh) ───
  if (scrollY <= evidenceBottom - vh) {
    const evidenceTrackLength = Math.max(100, evidenceBottom - scaleBottom);
    const rawEvidenceT = (scrollY - (scaleBottom - vh)) / evidenceTrackLength;
    const evidenceT = Math.max(0, Math.min(1, rawEvidenceT));
    return { type: "evidence_dive", t: evidenceT };
  }

  // ── ZONE 4: DEFERRED HOLD (scrollY > evidenceBottom - vh) ───
  return { type: "deferred_hold" };
}

export function solvePageSpaceRenderState(
  snapshot: ScrollSnapshot,
  prefersReducedMotion = false,
  frameOverride: string | null = null,
  transitionOverride: { name: string; t: number } | null = null
): ResolvedShotState {
  const position = compileTimelinePosition(snapshot, transitionOverride, frameOverride);
  return directShot(position, snapshot.viewportWidth, snapshot.viewportHeight, prefersReducedMotion);
}

// Aliases for compatibility
export type ExpandedResolvedRenderState = ResolvedShotState;
export const solveGlobalRenderState = solvePageSpaceRenderState;
