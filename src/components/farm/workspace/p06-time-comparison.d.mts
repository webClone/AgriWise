import type { WorkspaceState } from "./workspace-types";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
export interface EntityTemporalComparison {
  status: "no_selection" | "unavailable" | "scope_mismatch" | "matched";
  guidance: string;
  entityKind: string | null;
  entityId: string | null;
  epistemicClass: string | null;
  observedAt: string | null;
  firstAvailableAt: string | null;
  publishedAt: string | null;
  observationRelation: string;
  availabilityRelation: string;
  envelopeDigest: string | null;
  scientificReferenceQualified: boolean;
}
export function buildEntityTemporalComparison(args: {workspace: WorkspaceState; entity: WorkspaceFeatureEnvelope | null | undefined}): EntityTemporalComparison;
