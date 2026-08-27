import type { BrowserRenderReceipt } from "./render-materialization";

export type SourcePolicy = "satellite" | "experimental" | "asmae_diagnostic" | "hybrid";

export const SOURCE_POLICIES: readonly SourcePolicy[];

export function normalizeSourcePolicy(
  value: unknown,
  fallback?: SourcePolicy,
): SourcePolicy;

export function buildLayer10RequestIdentity(input: {
  sequence: number;
  plotId: string;
  sourcePolicy: SourcePolicy;
  visualIntensity: number;
  experimental1m: boolean;
}): string;

export function buildRenderViewIdentity(input: {
  publicationId?: string | null;
  plotId?: string | null;
  sourcePolicy: SourcePolicy;
  mode: string;
  surfaceType?: string | null;
  surfaceId?: string | null;
  overlaySurfaceType?: string | null;
  overlaySurfaceId?: string | null;
  overlayEnabled: boolean;
}): string;

export function hasCompleteCommittedRenderIdentity(input: {
  publicationId?: string | null;
  snapshotId?: string | null;
  surfaceInventoryHash?: string | null;
  renderAuthorizationVersion?: string | null;
  surfaceId?: string | null;
}): boolean;

export function shouldRetainLastKnownGood<
  T extends { plot_id: string; surfaces: unknown[] },
>(previous: T | null, candidate: T, plotId: string): boolean;

export function isLatestLayer10Request(
  activeSequence: number,
  candidateSequence: number,
  aborted?: boolean,
): boolean;

export function classifyCanonicalHeadValidation(
  validation?: Record<string, unknown> | null,
): "valid" | "stale" | "corrupt";

export function resolveCompoundRenderAttribution(input: {
  baseRendered: boolean;
  overlayRendered: boolean;
  baseSourceLabel: string;
  baseAuthorityLabel: string;
}): { sourceLabel: string; authorityLabel: string };

export function browserRenderReceiptSignature(
  receipt?: BrowserRenderReceipt | null,
): string;
