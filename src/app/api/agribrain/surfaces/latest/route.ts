/**
 * /api/agribrain/surfaces/latest — Cache-first surface endpoint
 * 
 * Returns the latest cached surfaces snapshot instantly.
 * 
 * Behavior:
 *   HIT   → return cached surfaces (< 50ms)
 *   STALE → return cached surfaces + trigger background refresh
 *   MISS  → return { status: "generating" } + trigger background run
 * 
 * The plot page should NEVER block on /v2/run for initial render.
 * This endpoint enables instant renders from cached data.
 */
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { gunzipSync } from "zlib";
import {
  PUBLICATION_STATUS,
  RENDER_AUTHORIZATION_VERSION,
  SURFACES_SCHEMA_VERSION,
  inspectSurfacePublication,
} from "@/lib/agribrain/surface-contract";
import { getSession } from "@/lib/session";

// Surfaces are considered stale after 1 hour
const STALE_THRESHOLD_MS = 60 * 60 * 1000;

function buildDefaultAsmaeProof() {
  return {
    sentinel_proof: { s2_real_scene_count: 0, s1_real_scene_count: 0, proxy_scene_count: 0 },
    weather_proof: { status: "unavailable", daily_count: 0 },
    enkf_proof: { full_enkf_credit_allowed: false, update_mode: "unavailable" },
    bma_proof: { production_bma_valid: false },
    ml_proof: { ml_production_weight: 0.0, ml_used_for_approval: false },
    resolution_proof: { field_approved_1m_mask_source: "unavailable" },
    feature_proof: { assimilated: [], missing: ["proof_unavailable"] },
  };
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { plotId, visualIntensity, sourcePolicy } = body;

    if (!plotId) {
      return NextResponse.json(
        { success: false, error: "plotId is required" },
        { status: 400 }
      );
    }

    const session = await getSession();
    const requestUserId = session?.userId || null;
    if (!requestUserId) {
      return NextResponse.json(
        { success: false, error: "Authentication required" },
        { status: 401 }
      );
    }

    const authorizedPlot = await prisma.plot.findFirst({
      where: {
        id: plotId,
        farm: { userId: requestUserId },
      },
      select: { id: true, farmId: true },
    });
    if (!authorizedPlot) {
      return NextResponse.json(
        { success: false, error: "Plot not found" },
        { status: 404 }
      );
    }

    const rawPolicy = sourcePolicy || "satellite";
    const normalizedSourcePolicy = rawPolicy === "asmae" ? "asmae_diagnostic" : rawPolicy;
    const cookieHeader = request.headers.get("cookie") || undefined;

    // 1. Find latest snapshot with surface data
    const snapshot = await prisma.intelligenceSnapshot.findFirst({
      where: { plotId, farmId: authorizedPlot.farmId },
      orderBy: { capturedAt: "desc" },
      select: {
        id: true,
        capturedAt: true,
        surfaceStats: true,
        surfaceDigest: true,
        surfaceGridsByPolicy: true,
        surfaceDigestByPolicy: true,
        surfaceGridsGz: true, // legacy
      },
    });

    // MISS — no cached surfaces exist
    const gridsMap = (snapshot?.surfaceGridsByPolicy as Record<string, any>) || {};
    // Every display policy reads the same complete scientific inventory.
    // Policy resolution happens locally from render authorizations.
    const canonicalInventoryKey = "canonical";
    const entry = gridsMap[canonicalInventoryKey];
    let targetGz: string | undefined = undefined;
    let cachedSourcePolicyDisplayState: any = null;
    let asmaeEvidenceState: any = null;
    let experimentalVisualLadder: any = null;
    let asmaeApprovalLadder: any = null;

    const hasInvalidPolicyEntry = entry !== undefined;

    if (entry && typeof entry === "object" && entry !== null) {
      if (
        entry.schemaVersion === SURFACES_SCHEMA_VERSION &&
        entry.inventoryPolicy === canonicalInventoryKey &&
        entry.sourcePolicyDisplayState &&
        entry.asmaeEvidenceState &&
        entry.experimentalVisualLadder !== undefined &&
        entry.surfaceInventory &&
        entry.displayStateByPolicyAndMode &&
        entry.render_authorization_version === RENDER_AUTHORIZATION_VERSION &&
        [PUBLICATION_STATUS.VALID_NORMAL, PUBLICATION_STATUS.VALID_DEGRADED].includes(entry.publicationStatus) &&
        entry.publicationId &&
        entry.publicationRunId &&
        entry.render_authorizations &&
        entry.asmae_proof &&
        Object.keys(entry.asmae_proof).length > 0
      ) {
        targetGz = entry.gz;
        cachedSourcePolicyDisplayState = entry.sourcePolicyDisplayState || null;
        asmaeEvidenceState = entry.asmaeEvidenceState || null;
        experimentalVisualLadder = entry.experimentalVisualLadder || null;
        asmaeApprovalLadder = entry.asmaeApprovalLadder || null;
      } else {
        console.warn(`[Surfaces Latest] Invalidating canonical inventory due to schema version mismatch or missing display lock states.`, entry);
        targetGz = undefined;
      }
    } else {
      targetGz = undefined;
    }

    if (!snapshot || !targetGz) {
      return NextResponse.json({
        status: "generating",
        ...(hasInvalidPolicyEntry
          ? {
              publication_status: PUBLICATION_STATUS.INVALID_PUBLICATION,
              publication_reason: "canonical_inventory_entry_invalid",
            }
          : {}),
        message: "Generating intelligence… Raw plot data is available while AgriBrain prepares surfaces.",
        plotId,
      });
    }

    // 2. Decompress cached surfaces
    let parsed: any = null;
    try {
      const compressed = Buffer.from(targetGz, "base64");
      const decompressed = gunzipSync(compressed);
      parsed = JSON.parse(decompressed.toString("utf-8"));
    } catch (decompressErr) {
      console.warn("[Surfaces Latest] Failed to decompress cached grids:", decompressErr);
      try {
        const updatedGridsMap = { ...((snapshot.surfaceGridsByPolicy as Record<string, any>) || {}) };
        delete updatedGridsMap[canonicalInventoryKey];

        const updatedDigestMap = { ...((snapshot.surfaceDigestByPolicy as Record<string, any>) || {}) };
        delete updatedDigestMap[canonicalInventoryKey];

        await prisma.intelligenceSnapshot.update({
          where: { id: snapshot.id },
          data: {
            surfaceGridsGz: null,
            surfaceDigest: null,
            surfaceGridsByPolicy: updatedGridsMap,
            surfaceDigestByPolicy: updatedDigestMap,
          },
        });
      } catch (updErr) {
        console.error("[Surfaces Latest] Failed to invalidate corrupt compressed cache:", updErr);
      }
      return NextResponse.json({
        status: "generating",
        publication_status: PUBLICATION_STATUS.FAILED_PUBLICATION,
        publication_reason: "compressed_publication_unreadable",
        message: "Cached data corrupted, regenerating…",
        plotId,
      });
    }

    // A policy-specific payload is scientifically incomplete under the
    // canonical-inventory architecture and must be regenerated.
    const cachedPolicy = parsed?.source_policy;
    if (parsed && cachedPolicy !== canonicalInventoryKey) {
      return NextResponse.json({
        status: "policy_mismatch",
        surface_cache_status: "policy_mismatch",
        requested_source_policy: normalizedSourcePolicy,
        cached_source_policy: cachedPolicy,
        served_surface: null,
        fallback_allowed: true
      });
    }

    let cacheValid = true;
    const asmaeEnabled = (process.env.ASMAE_ENABLED || "false").toLowerCase();
    const l10AsmaeSurfacesEnabled = (process.env.L10_ASMAE_SURFACES_ENABLED || "false").toLowerCase();
    const l10AsmaeDiagnosticAliasesEnabled = (process.env.L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED || "false").toLowerCase();
    const surfaceLadderPolicyVersion = process.env.SURFACE_LADDER_POLICY_VERSION || "v1";
    const renderPolicyVersion = process.env.RENDER_POLICY_VERSION || "v1";
    const modeSurfacePlanVersion = process.env.MODE_SURFACE_PLAN_VERSION || "v1";
    const displayGridPolicyVersion = process.env.DISPLAY_GRID_POLICY_VERSION || "v1";

    if (!parsed) {
      cacheValid = false;
    } else {
      const publicationInspection = inspectSurfacePublication(parsed);
      const payloadVersion = parsed.version || parsed.schema_version || parsed.schemaVersion;
      const hasSurfaces = Array.isArray(parsed.surfaces) && parsed.surfaces.length > 0;
      const terminalNoData =
        Array.isArray(parsed.surfaces) &&
        parsed.surfaces.length === 0 &&
        (parsed.placeholder_only === true ||
          parsed.status === "degraded" ||
          parsed.degradation_mode === "DATA_GAP" ||
          parsed.quality?.degradation_mode === "DATA_GAP");
      
      const hasWrapperMetadata = 
        parsed.plot_id &&
        parsed.run_id &&
        parsed.generated_at;

      const hasCompressedMetadata = 
        parsed.histograms &&
        parsed.quality &&
        parsed.mode_surface_plan &&
        parsed.surface_inventory &&
        parsed.mode_display_state;

      const hasSourcePolicyDisplayState = 
        parsed.source_policy_display_state && 
        typeof parsed.source_policy_display_state === "object" &&
        Object.keys(parsed.source_policy_display_state).length > 0;

      const hasAsmaeEvidenceState =
        (parsed.asmae_evidence_state && Object.keys(parsed.asmae_evidence_state).length > 0) ||
        (parsed.source_policy_display_state?.asmae_evidence_state && Object.keys(parsed.source_policy_display_state.asmae_evidence_state).length > 0) ||
        (asmaeEvidenceState && Object.keys(asmaeEvidenceState).length > 0);

      const hasDisplayStateByPolicyAndMode =
        parsed.displayStateByPolicyAndMode &&
        typeof parsed.displayStateByPolicyAndMode === "object";

      const hasExperimentalVisualLadder =
        parsed.experimentalVisualLadder !== undefined ||
        parsed.source_policy_display_state?.experimentalVisualLadder !== undefined ||
        cachedSourcePolicyDisplayState?.experimentalVisualLadder !== undefined ||
        experimentalVisualLadder !== undefined;

      const hasSurfaceStats = snapshot?.surfaceStats && typeof snapshot.surfaceStats === "object" && Object.keys(snapshot.surfaceStats).length > 0;
      const statsEmptyWhenSurfacesExist = hasSurfaces && !hasSurfaceStats;

      const hasSurfaceInventory = 
        parsed.surface_inventory && 
        typeof parsed.surface_inventory === "object" && 
        Object.keys(parsed.surface_inventory).length > 0;

      const hasCompressedTruthMetadata = 
        Array.isArray(parsed.surfaces) && 
        parsed.surfaces.every((s: any) => 
          s && 
          typeof s === "object" && 
          s.grounding_class && 
          s.provenance && 
          typeof s.provenance === "object"
        );

      const hasWrapperTruthMetadata = 
        snapshot?.surfaceStats && 
        typeof snapshot.surfaceStats === "object";

      if (!publicationInspection.valid) {
        cacheValid = false;
      } else if (
        entry.publicationStatus !== parsed.publication_status ||
        entry.publicationId !== parsed.publication_id ||
        entry.publicationRunId !== parsed.publication_run_id
      ) {
        cacheValid = false;
      } else if (payloadVersion !== SURFACES_SCHEMA_VERSION) {
        cacheValid = false;
      } else if (!hasSurfaces && !terminalNoData) {
        cacheValid = false;
      } else if (!hasWrapperMetadata) {
        cacheValid = false;
      } else if (!hasCompressedMetadata && !terminalNoData) {
        cacheValid = false;
      } else if (!hasSourcePolicyDisplayState) {
        cacheValid = false;
      } else if (!hasAsmaeEvidenceState) {
        cacheValid = false;
      } else if (!hasExperimentalVisualLadder) {
        cacheValid = false;
      } else if (!hasSurfaceInventory && !terminalNoData) {
        cacheValid = false;
      } else if (!hasDisplayStateByPolicyAndMode) {
        cacheValid = false;
      } else if (!hasCompressedTruthMetadata) {
        cacheValid = false;
      } else if (!hasWrapperTruthMetadata) {
        cacheValid = false;
      } else if (statsEmptyWhenSurfacesExist) {
        cacheValid = false;
      } else if (parsed.render_authorization_version !== RENDER_AUTHORIZATION_VERSION) {
        cacheValid = false;
      } else if (!parsed.render_authorizations || typeof parsed.render_authorizations !== "object" || Object.keys(parsed.render_authorizations).length === 0) {
        cacheValid = false;
      } else if (!parsed.asmae_proof || typeof parsed.asmae_proof !== "object" || Object.keys(parsed.asmae_proof).length === 0) {
        cacheValid = false;
      } else if (
        parsed.asmae_enabled !== asmaeEnabled ||
        parsed.l10_asmae_surfaces_enabled !== l10AsmaeSurfacesEnabled ||
        parsed.l10_asmae_diagnostic_aliases_enabled !== l10AsmaeDiagnosticAliasesEnabled ||
        parsed.surface_ladder_policy_version !== surfaceLadderPolicyVersion ||
        parsed.render_policy_version !== renderPolicyVersion ||
        parsed.mode_surface_plan_version !== modeSurfacePlanVersion ||
        parsed.display_grid_policy_version !== displayGridPolicyVersion
      ) {
        cacheValid = false;
      } else if (visualIntensity !== undefined && Math.abs((parsed.visual_intensity ?? 0.40) - visualIntensity) > 0.01) {
        cacheValid = false;
      } else {
        for (const s of parsed.surfaces) {
          if (!s || typeof s !== "object") {
            cacheValid = false;
            break;
          }
          if (!s.type && !s.semantic_type) {
            cacheValid = false;
            break;
          }
          if (!s.grounding_class) {
            cacheValid = false;
            break;
          }
          if (!s.values && !s.grid_b64) {
            cacheValid = false;
            break;
          }
          if (Array.isArray(s.values)) {
            if (s.values.length === 0) {
              cacheValid = false;
              break;
            }
            const rowLen = Array.isArray(s.values[0]) ? s.values[0].length : 0;
            for (const row of s.values) {
              if (!Array.isArray(row) || row.length !== rowLen) {
                cacheValid = false;
                break;
              }
            }
            if (!cacheValid) break;

            const stype = s.semantic_type || s.type || "";
            if (stype === "RESOLUTION_COVERAGE") {
              const allowedRes = new Set([0, 1, 2, 3, 4, 5]);
              for (const row of s.values) {
                for (const val of row) {
                  if (val !== null && val !== undefined && !allowedRes.has(val)) {
                    cacheValid = false;
                    break;
                  }
                }
                if (!cacheValid) break;
              }
            } else if (stype === "EXPERIMENTAL_FINE_DETAIL_CANDIDATE") {
              const allowedExp = new Set([0, 1]);
              for (const row of s.values) {
                for (const val of row) {
                  if (val !== null && val !== undefined && !allowedExp.has(val)) {
                    cacheValid = false;
                    break;
                  }
                }
                if (!cacheValid) break;
              }
            }
            if (!cacheValid) break;
          }
        }

        if (cacheValid) {
          const surfaceTypes = new Set(
            parsed.surfaces.map((s: any) => s.semantic_type || s.type || "")
          );
          if (surfaceTypes.has("NDVI_CLEAN")) {
            for (const requiredMask of [
              "OBSERVED_DATA_MASK_NDVI",
              "GAP_FILL_MASK_NDVI",
              "VALID_DATA_MASK_NDVI",
            ]) {
              if (!surfaceTypes.has(requiredMask)) {
                cacheValid = false;
                break;
              }
            }
          }
        }

        if (cacheValid) {
          const hasExperimentalCandidate = parsed.surfaces.some(
            (s: any) => (s.semantic_type || s.type || "") === "EXPERIMENTAL_FINE_DETAIL_CANDIDATE"
          );
          if (hasExperimentalCandidate) {
            const baseTypes = new Set(
              parsed.surfaces.map((s: any) => s.semantic_type || s.type || "")
            );
            for (const requiredExp of [
              "EXPERIMENTAL_VISUAL_CANOPY",
              "EXPERIMENTAL_TEXTURE_SUPPORT_MASK",
            ]) {
              if (!baseTypes.has(requiredExp)) {
                cacheValid = false;
                break;
              }
            }
          }
        }
      }
    }

    if (!cacheValid) {
      console.warn(`[Surfaces Latest] Corrupt or legacy cache payload detected for snapshot ${snapshot.id}. Invalidating canonical surface inventory.`);
      try {
        const updatedGridsMap = { ...((snapshot.surfaceGridsByPolicy as Record<string, any>) || {}) };
        delete updatedGridsMap[canonicalInventoryKey];

        const updatedDigestMap = { ...((snapshot.surfaceDigestByPolicy as Record<string, any>) || {}) };
        delete updatedDigestMap[canonicalInventoryKey];

        await prisma.intelligenceSnapshot.update({
          where: { id: snapshot.id },
          data: {
            surfaceGridsGz: null,
            surfaceDigest: null,
            surfaceGridsByPolicy: updatedGridsMap,
            surfaceDigestByPolicy: updatedDigestMap,
          },
        });
      } catch (updErr) {
        console.error("[Surfaces Latest] Failed to invalidate surface cache:", updErr);
      }
      return NextResponse.json({
        status: "generating",
        publication_status: PUBLICATION_STATUS.INVALID_PUBLICATION,
        publication_reason: "cached_publication_contract_invalid",
        message: "Cached data legacy or corrupted, regenerating…",
        plotId,
      });
    }

    const surfaceGrids = parsed.surfaces || [];

    const compactGrids = surfaceGrids.map((surface: any) => {
      if (!Array.isArray(surface?.values) || surface.values.length === 0) {
        return surface;
      }
      const height = surface.values.length;
      const width = surface.values[0]?.length || 0;
      if (width === 0) return surface;

      const float32 = new Float32Array(height * width);
      for (let r = 0; r < height; r++) {
        for (let c = 0; c < width; c++) {
          const v = surface.values[r]?.[c];
          float32[r * width + c] = v === null || v === undefined ? NaN : Number(v);
        }
      }

      const b64 = Buffer.from(float32.buffer).toString("base64");
      const { values: _values, ...rest } = surface;
      return { ...rest, grid_b64: b64, grid_width: width, grid_height: height };
    });

    const ageMs = Date.now() - new Date(snapshot.capturedAt).getTime();
    const isStale = ageMs > STALE_THRESHOLD_MS;

    if (isStale) {
      triggerBackgroundSurfaceRun(plotId, visualIntensity, normalizedSourcePolicy, cookieHeader);
    }

    return NextResponse.json({
      status: isStale ? "stale" : "fresh",
      publication_status: parsed.publication_status,
      publication_id: parsed.publication_id,
      publication_run_id: parsed.publication_run_id,
      request_run_id: parsed.request_run_id || null,
      plotId,
      capturedAt: snapshot.capturedAt,
      surfaceStats: snapshot.surfaceStats,
      surfaceDigest: snapshot.surfaceDigest,
      surfaceGrids: compactGrids,
      zones: parsed.zones || [],
      histograms: parsed.histograms || {},
      quality: parsed.quality || {},
      rendering_quality: parsed.rendering_quality || parsed.quality || {},
      scientific_pipeline_quality: parsed.scientific_pipeline_quality || parsed.global_quality || {},
      global_quality: parsed.global_quality || parsed.scientific_pipeline_quality || {},
      layer_results: parsed.layer_results || {},
      fallback_guidance: parsed.fallback_guidance || {},
      explainability_pack: parsed.explainability_pack || {},
      ground_truth_summary: parsed.ground_truth_summary || null,
      visual_source: parsed.visual_source || null,
      mode_surface_plan: parsed.mode_surface_plan || {},
      surface_inventory: parsed.surface_inventory || {},
      displayStateByPolicyAndMode: parsed.displayStateByPolicyAndMode || (entry && typeof entry === "object" ? entry.displayStateByPolicyAndMode : null) || {},
      mode_display_state: parsed.mode_display_state || {},
      source_policy_display_state: {
        ...(parsed.source_policy_display_state || cachedSourcePolicyDisplayState || {}),
        requested_policy: normalizedSourcePolicy,
        resolved_policy: normalizedSourcePolicy,
        resolution_scope: "local_view_over_canonical_inventory",
        canonical_inventory: true,
        experimentalVisualLadder: experimentalVisualLadder || parsed.experimentalVisualLadder || parsed.source_policy_display_state?.experimentalVisualLadder || null,
        asmaeApprovalLadder: asmaeApprovalLadder || parsed.asmaeApprovalLadder || parsed.source_policy_display_state?.asmaeApprovalLadder || null,
      },
      asmae_evidence_state: asmaeEvidenceState || parsed.asmae_evidence_state || parsed.source_policy_display_state?.asmae_evidence_state || null,
      core_asmae_evidence_state: parsed.core_asmae_evidence_state || entry?.coreAsmaeEvidenceState || asmaeEvidenceState || parsed.asmae_evidence_state || null,
      publication_surface_state: parsed.publication_surface_state || entry?.publicationSurfaceState || {},
      publication_demotion: parsed.publication_demotion || entry?.publicationDemotion || {},
      asmae_feature_pack: parsed.asmae_feature_pack || entry?.asmaeFeaturePack || entry?.asmae_feature_pack || {},
      provenance: parsed.provenance || {},
      surface_behavior_proof: parsed.surface_behavior_proof || entry?.surface_behavior_proof || {},
      display_trace: parsed.display_trace || entry?.display_trace || {},
      asmae_proof: (parsed.asmae_proof && Object.keys(parsed.asmae_proof).length > 0) ? parsed.asmae_proof : (entry?.asmae_proof && Object.keys(entry.asmae_proof).length > 0 ? entry.asmae_proof : buildDefaultAsmaeProof()),
      render_authorizations: parsed.render_authorizations || entry?.render_authorizations || {},
      render_authorization_version: parsed.render_authorization_version || entry?.render_authorization_version || "",
      intelligence_snapshot_id: parsed.intelligence_snapshot_id || snapshot.id,
      agribrain_run_id: parsed.agribrain_run_id || "",
      generated_at: parsed.generated_at || snapshot.capturedAt,
      source_window: parsed.source_window || [],
      surface_schema_version: parsed.surface_schema_version || parsed.schema_version || "",
      temporal_evidence_contract_version: parsed.temporal_evidence_contract_version || "",
      requested_source_policy: normalizedSourcePolicy,
      inventory_source_policy: canonicalInventoryKey,
      ageMs,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[Surfaces Latest] Error:", message);
    return NextResponse.json(
      { success: false, error: `Failed to load surfaces: ${message}` },
      { status: 500 }
    );
  }
}

function triggerBackgroundSurfaceRun(plotId: string, visualIntensity?: number, sourcePolicy?: string, cookieHeader?: string) {
  const baseUrl = process.env.NODE_ENV === "development"
    ? "http://127.0.0.1:3000"
    : (process.env.NEXTAUTH_URL || process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000");

  fetch(`${baseUrl}/api/agribrain/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
    },
    body: JSON.stringify({ plotId, mode: "surfaces", query: "", visualIntensity, sourcePolicy }),
  }).catch((err) => {
    console.warn("[Surfaces Latest] Background run trigger failed:", err);
  });
}
