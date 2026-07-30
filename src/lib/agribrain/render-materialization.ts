import {
  getRenderAuthorization,
  type RenderAuthorization,
  type RenderRole,
} from "./source-policy-display-resolver";

export const RENDER_AUTHORIZATION_VERSION = "v924_bc10_18_render_auth_v1";

export type RenderMaterializationStatus =
  | "rendered"
  | "blocked_invalid_grid"
  | "blocked_missing_mask"
  | "blocked_unauthorized"
  | "blocked_image_generation";

export interface RenderMaterializationReceipt {
  publicationId: string;
  sourceId: string;
  layerId: string;
  renderKind: string;
  timestamp: string;
  mapInstanceId: string;
}

export interface RenderMaterializationResult {
  status: RenderMaterializationStatus;
  surfaceType: string;
  policy: string;
  mode: string;
  role: RenderRole;
  reason: string;
  layerId: string | null;
  gridBounds: [number, number, number, number] | null;
  gridWidth: number | null;
  gridHeight: number | null;
  receipt?: RenderMaterializationReceipt | null;
}

/**
 * The single browser-side receipt for a committed map view. Preflight
 * authorization is deliberately kept separate from this post-layer result.
 */
export interface BrowserRenderReceipt {
  viewIdentity: string;
  baseMaterialization: RenderMaterializationResult;
  overlayMaterialization: RenderMaterializationResult;
  committedAt: string;
}

export interface MaterializationSurface {
  type?: string;
  semantic_type?: string;
  values?: unknown[][];
  grid_spec?: MaterializationGridSpec | null;
  display_grid_spec?: MaterializationGridSpec | null;
  provenance?: Record<string, unknown> | null;
}

export interface MaterializationGridSpec {
  crs?: string;
  bounds?: number[];
  transform?: number[];
  width?: number;
  height?: number;
}

interface MaterializationInput {
  surface?: MaterializationSurface | null;
  plotGeoJson?: unknown;
  policy: string;
  mode: string;
  role: RenderRole;
  renderAuthorizationVersion?: string | null;
  renderAuthorizations?: unknown;
  observedMaskSurface?: MaterializationSurface | null;
  gapFillMaskSurface?: MaterializationSurface | null;
  modeDisplayState?: Record<string, unknown> | null;
  layerId?: string;
}

interface ValidatedGrid {
  valid: boolean;
  reason: string;
  bounds: [number, number, number, number] | null;
  width: number | null;
  height: number | null;
}

function finiteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function getGridSpec(s?: MaterializationSurface | null): MaterializationGridSpec | null {
  if (!s) return null;
  const prov = s.provenance as Record<string, unknown> | undefined;
  return s.display_grid_spec || s.grid_spec || (prov?.grid_spec as MaterializationGridSpec) || (prov?.display_grid_spec as MaterializationGridSpec) || null;
}

export function validateSurfaceGrid(
  surface?: MaterializationSurface | null,
  plotGeoJson?: unknown
): ValidatedGrid {
  if (!surface || !surface.values || !Array.isArray(surface.values) || surface.values.length === 0) {
    return { valid: false, reason: "surface_values_empty", bounds: null, width: null, height: null };
  }
  const height = surface.values.length;
  const firstRow = surface.values[0];
  if (!Array.isArray(firstRow) || firstRow.length === 0) {
    return { valid: false, reason: "surface_values_first_row_empty", bounds: null, width: null, height };
  }
  const width = firstRow.length;
  const isUniformRowLen = surface.values.every((row) => Array.isArray(row) && row.length === width);
  if (!isUniformRowLen) {
    return { valid: false, reason: "surface_values_non_rectangular", bounds: null, width: null, height };
  }

  const spec = getGridSpec(surface);
  if (!spec || !spec.bounds || !Array.isArray(spec.bounds) || spec.bounds.length !== 4) {
    return { valid: false, reason: "grid_spec_bounds_invalid", bounds: null, width, height };
  }

  const [minLng, minLat, maxLng, maxLat] = spec.bounds.map(Number);
  if (!Number.isFinite(minLng) || !Number.isFinite(minLat) || !Number.isFinite(maxLng) || !Number.isFinite(maxLat)) {
    return { valid: false, reason: "grid_spec_bounds_non_finite", bounds: null, width, height };
  }
  if (minLng >= maxLng || minLat >= maxLat) {
    return { valid: false, reason: "grid_spec_bounds_collapsed", bounds: null, width, height };
  }

  return {
    valid: true,
    reason: "grid_valid",
    bounds: [minLng, minLat, maxLng, maxLat],
    width,
    height,
  };
}

export function canMaterializeMask(
  mask?: MaterializationSurface | null,
  target?: MaterializationSurface | null,
  allowNearestSharedBounds = false,
  plotGeoJson?: unknown
): boolean {
  if (!mask) return false;
  const maskGrid = validateSurfaceGrid(mask, plotGeoJson);
  if (!maskGrid.valid) return false;
  if (!target) return true;
  const targetGrid = validateSurfaceGrid(target, plotGeoJson);
  if (!maskGrid.valid || !targetGrid.valid || !maskGrid.bounds || !targetGrid.bounds) return false;

  const maskSpec = getGridSpec(mask);
  const targetSpec = getGridSpec(target);
  if (!maskSpec || !targetSpec || String(maskSpec.crs || "") !== String(targetSpec.crs || "")) return false;

  const sharedBounds = maskGrid.bounds.every((value, index) => {
    const targetValue = targetGrid.bounds?.[index];
    if (!Number.isFinite(targetValue)) return false;
    const scale = Math.max(1, Math.abs(value), Math.abs(targetValue as number));
    return Math.abs(value - (targetValue as number)) <= scale * 1e-8;
  });
  if (!sharedBounds) return false;
  if (maskGrid.width === targetGrid.width && maskGrid.height === targetGrid.height) {
    return true;
  }
  return allowNearestSharedBounds;
}

function blocked(
  input: MaterializationInput,
  surfaceType: string,
  status: RenderMaterializationStatus,
  reason: string,
  grid?: ValidatedGrid
): RenderMaterializationResult {
  return {
    status,
    surfaceType,
    policy: input.policy,
    mode: input.mode,
    role: input.role,
    reason,
    layerId: null,
    gridBounds: grid?.bounds ?? null,
    gridWidth: grid?.width ?? null,
    gridHeight: grid?.height ?? null,
    receipt: null,
  };
}

export function resolveRenderMaterialization(input: MaterializationInput): RenderMaterializationResult {
  const surfaceType = String(input.surface?.semantic_type || input.surface?.type || "");
  if (!surfaceType || !input.surface) {
    return blocked(input, surfaceType, "blocked_image_generation", "missing_surface");
  }

  const auth: RenderAuthorization = getRenderAuthorization(
    surfaceType,
    input.policy,
    input.mode,
    input.role,
    input.renderAuthorizations,
  );
  if (!auth.authorized) {
    return blocked(input, surfaceType, "blocked_unauthorized", auth.reason || "missing_render_authorization");
  }

  const allowedKind = input.role === "base"
    ? auth.renderKind === "full_raster" || auth.renderKind === "diagnostic_overlay"
    : input.role === "overlay"
      ? auth.renderKind === "proxy_overlay" || auth.renderKind === "diagnostic_overlay"
      : input.role === "candidate"
        ? auth.renderKind === "proxy_overlay" || auth.renderKind === "diagnostic_overlay"
        : false;
  if (!allowedKind) {
    return blocked(input, surfaceType, "blocked_unauthorized", `unauthorized_render_kind:${auth.renderKind}`);
  }

  const modeState = input.modeDisplayState?.[input.mode]
    ? (input.modeDisplayState[input.mode] as Record<string, unknown>)
    : input.modeDisplayState;

  const isAsmaeDiag = input.policy === "asmae_diagnostic" || auth.renderKind === "diagnostic_overlay";

  if (modeState && !isAsmaeDiag && (
    modeState.spatial === false
    || modeState.canRenderPixels === false
    || modeState.renderKind === "card_only"
    || modeState.renderKind === "none"
  )) {
    return blocked(
      input,
      surfaceType,
      "blocked_invalid_grid",
      String(modeState.reason || modeState.grid_spec_status || "mode_not_spatial"),
    );
  }

  const grid = validateSurfaceGrid(input.surface, input.plotGeoJson);
  if (!grid.valid || !grid.width || !grid.height) {
    return blocked(input, surfaceType, "blocked_invalid_grid", grid.reason, grid);
  }

  const nearestSharedBounds = auth.maskAlignmentPolicy === "nearest_shared_bounds" || isAsmaeDiag;
  if (!isAsmaeDiag && auth.requiresObservedMask && !canMaterializeMask(
    input.observedMaskSurface,
    input.surface,
    nearestSharedBounds,
    input.plotGeoJson,
  )) {
    return blocked(input, surfaceType, "blocked_missing_mask", auth.observedMaskType || "observed_mask_missing_or_misaligned", grid);
  }
  if (!isAsmaeDiag && auth.requiresGapFillMask && !canMaterializeMask(
    input.gapFillMaskSurface,
    input.surface,
    nearestSharedBounds,
    input.plotGeoJson,
  )) {
    return blocked(input, surfaceType, "blocked_missing_mask", auth.gapFillMaskType || "gap_fill_mask_missing_or_misaligned", grid);
  }

  const hasFinitePixel = input.surface.values?.some((row) =>
    row.some((value) => finiteNumber(value)),
  );
  if (!hasFinitePixel) {
    return blocked(input, surfaceType, "blocked_image_generation", "surface_has_no_finite_pixels", grid);
  }

  return blocked(input, surfaceType, "blocked_image_generation", "image_layer_not_created", grid);
}

export function finalizeRenderMaterialization(
  preflight: RenderMaterializationResult,
  layer: unknown,
  layerId: string,
  receiptDetails?: Partial<RenderMaterializationReceipt>
): RenderMaterializationResult {
  if (preflight.reason !== "image_layer_not_created") return preflight;
  const hasLayer = Array.isArray(layer) ? layer.length > 0 && layer.every(Boolean) : !!layer;
  if (!hasLayer) return preflight;

  const receipt: RenderMaterializationReceipt = {
    publicationId: receiptDetails?.publicationId || "pub_canonical",
    sourceId: receiptDetails?.sourceId || `src_${layerId}`,
    layerId,
    renderKind: receiptDetails?.renderKind || preflight.surfaceType || "unknown",
    timestamp: receiptDetails?.timestamp || new Date().toISOString(),
    mapInstanceId: receiptDetails?.mapInstanceId || "map_primary",
  };

  return {
    ...preflight,
    status: "rendered",
    reason: "layer_created",
    layerId,
    receipt,
  };
}

export function isRenderedMaterialization(
  result?: RenderMaterializationResult | null,
  surfaceType?: string | null,
): boolean {
  return !!result
    && result.status === "rendered"
    && (!surfaceType || result.surfaceType === surfaceType);
}

export function isZoneSpatiallyAuthorized(
  zone: Record<string, unknown>,
  materialization: RenderMaterializationResult | null | undefined,
  gridHeight: number,
  gridWidth: number,
): boolean {
  if (!isRenderedMaterialization(materialization)) return false;

  const validity = zone.grid_validity;
  const validityIsValid = typeof validity === "string"
    ? validity.toLowerCase() === "valid"
    : !!validity
      && typeof validity === "object"
      && (
        (validity as Record<string, unknown>).valid === true
        || String((validity as Record<string, unknown>).status || "").toLowerCase() === "valid"
      );
  if (!validityIsValid) return false;

  const authority = String(zone.authority || "").toLowerCase();
  if (authority !== "management_zone" && authority !== "algorithmic_scouting_region") return false;
  if (zone.authority_block_reason) return false;

  const sourceType = String(zone.source_surface_type || "");
  if (!sourceType || sourceType !== materialization?.surfaceType) return false;

  const cells = zone.cell_indices;
  if (!Array.isArray(cells) || cells.length === 0) return false;
  return cells.every((cell) =>
    Array.isArray(cell)
    && cell.length === 2
    && Number.isInteger(cell[0])
    && Number.isInteger(cell[1])
    && cell[0] >= 0
    && cell[0] < gridHeight
    && cell[1] >= 0
    && cell[1] < gridWidth,
  );
}
