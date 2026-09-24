import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";
import { classifyCanonicalHeadValidation } from "@/lib/agribrain/layer10-request-state.mjs";

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

async function handleSurfacesRequest(request: NextRequest, plotIdParam?: string) {
  let plotId = plotIdParam;
  if (!plotId) {
    try {
      const body = await request.json();
      plotId = body.plotId;
    } catch {
      plotId = request.nextUrl.searchParams.get("plotId") || undefined;
    }
  }

  if (!plotId) {
    return NextResponse.json({ success: false, error: "plotId is required" }, { status: 400 });
  }

  const access = await authorizePlot(plotId);
  if (access.status !== 200 || !access.plot) {
    return NextResponse.json(
      { success: false, error: access.status === 401 ? "Authentication required" : "Plot not found" },
      { status: access.status }
    );
  }

  const authorizedPlot = access.plot;
  const tenantId = authorizedPlot.farm.userId || access.userId!;

  const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

  // 1. Primary path: fetch validated canonical plot snapshot head from Python
  try {
    const pathname = `/v2/plots/${encodeURIComponent(plotId)}/snapshot`;
    const signedHeaders = buildSignedInternalHeaders(
      "GET",
      pathname,
      {
        tenantId,
        farmId: authorizedPlot.farmId,
        plotId,
      }
    );

    const snapRes = await fetch(`${apiUrl}${pathname}`, {
      headers: {
        ...signedHeaders,
        "Cache-Control": "no-cache",
      },
      next: { revalidate: 0 },
    });

    if (snapRes.ok) {
      const snapJson = await snapRes.json();
      if (snapJson?.available === false && snapJson?.refreshRequired === true) {
        return NextResponse.json({
          ...snapJson,
          status: "stale",
          reason: snapJson.reason || "canonical_head_schema_stale",
        });
      }
      if (snapJson && snapJson.available !== false && snapJson.frontend_payload) {
        // Assert Python validation flags
        const validation = snapJson.validation || {};
        const validationState = classifyCanonicalHeadValidation(validation);
        if (validationState === "corrupt") {
          return NextResponse.json(
            {
              available: false,
              reason: "canonical_head_validation_failed",
              validation,
              error: "Canonical publication head failed integrity validation",
            },
            { status: 409 }
          );
        }
        if (validationState === "stale") {
          return NextResponse.json({
            available: false,
            reason: "canonical_head_schema_stale",
            status: "stale",
            refreshRequired: true,
            validation,
            contract_validation: snapJson.contract_validation || {},
            plotId,
          });
        }

        const payload = snapJson.frontend_payload;
        return NextResponse.json({
          ...payload,
          publication_id: payload.publication_id || snapJson.frontend_publication_hash || "",
          intelligence_snapshot_id: payload.intelligence_snapshot_id || snapJson.snapshot_id,
          surface_inventory_hash: payload.surface_inventory_hash || snapJson.surface_inventory_hash || "",
          canonical_publication_receipt_hash: snapJson.publication_receipt_hash || "",
          canonical_publication_job_id: snapJson.publication_job_id || "",
          status: "fresh",
          capturedAt: snapJson.recorded_at || snapJson.timestamp || new Date().toISOString(),
          surfaceDigest: snapJson.node_hash || snapJson.snapshot_id,
          surfaceGrids: payload.surfaces || payload.surface_pack || [],
          zones: payload.zones || [],
          histograms: payload.histograms || {},
          validation,
        });
      }
    }
  } catch (err) {
    console.warn("[Surfaces Latest] Failed to fetch canonical snapshot head:", err);
  }

  // 2. Secondary fallback: fetch operational workerState (NO Prisma scientific head fallback)
  try {
    const progressPathname = `/v2/progress/${encodeURIComponent(plotId)}`;
    const signedHeaders = buildSignedInternalHeaders(
      "GET",
      progressPathname,
      {
        tenantId,
        farmId: authorizedPlot.farmId,
        plotId,
      }
    );

    const progRes = await fetch(`${apiUrl}${progressPathname}`, {
      headers: {
        ...signedHeaders,
        "Cache-Control": "no-cache",
      },
      next: { revalidate: 0 },
    });

    if (progRes.ok) {
      const workerState = await progRes.json();
      return NextResponse.json({
        available: false,
        reason: "canonical_head_not_published",
        status: "generating",
        workerState,
        plotId,
      });
    }
  } catch (err) {
    console.warn("[Surfaces Latest] Failed to fetch live worker state:", err);
  }

  return NextResponse.json({
    available: false,
    reason: "canonical_head_unavailable",
    status: "generating",
    plotId,
  });
}

export async function GET(request: NextRequest) {
  const plotId = request.nextUrl.searchParams.get("plotId") || undefined;
  return handleSurfacesRequest(request, plotId);
}

export async function POST(request: NextRequest) {
  return handleSurfacesRequest(request);
}
