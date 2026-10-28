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
  let plotId = plotIdParam || request.nextUrl.searchParams.get("plotId") || undefined;
  let snapshotId = request.nextUrl.searchParams.has("snapshotId")
    ? (request.nextUrl.searchParams.get("snapshotId") ?? "") : undefined;
  if (request.method === "POST") {
    try {
      const body = await request.json();
      plotId = plotId || (typeof body?.plotId === "string" ? body.plotId : undefined);
      snapshotId = snapshotId || (typeof body?.snapshotId === "string" ? body.snapshotId : undefined);
    } catch {
      // Retain query parameters if the request has no JSON body.
    }
  }
  // Exact reads must never silently fall back to a newer or different plot head.
  if (snapshotId !== undefined && !snapshotId.trim()) {
    return NextResponse.json({ available: false, error: "snapshotId cannot be blank" }, { status: 400 });
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
    const pathname = snapshotId
      ? `/v2/snapshots/${encodeURIComponent(snapshotId)}`
      : `/v2/plots/${encodeURIComponent(plotId)}/snapshot`;
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

    if (snapshotId && !snapRes.ok) {
      return NextResponse.json({
        available: false,
        status: "unavailable",
        reason: snapRes.status === 409
          ? "requested_snapshot_superseded_or_invalid" : "requested_snapshot_unavailable",
        snapshotId,
      }, { status: snapRes.status === 404 ? 404 : snapRes.status === 409 ? 409 : 502 });
    }

    if (snapRes.ok) {
      const snapJson = await snapRes.json();
      if (snapshotId) {
        const exactMatch = String(snapJson?.snapshot_id || "") === snapshotId;
        const plotMatch = String(snapJson?.plot_id || "") === plotId;
        if (!exactMatch || !plotMatch || snapJson?.available === false) {
          return NextResponse.json({
            available: false,
            reason: "requested_snapshot_identity_mismatch",
            status: "quarantined",
            snapshotId,
          }, { status: 409 });
        }
      }
      if (snapJson?.available === false && snapJson?.refreshRequired === true) {
        return NextResponse.json({
          ...snapJson,
          status: "stale",
          reason: snapJson.reason || "canonical_head_schema_stale",
        });
      }
      if (snapJson && snapJson.available !== false && snapJson.frontend_payload) {
        // The exact snapshot must pass the same publication integrity gates
        // as the current plot head; a namespace match alone is insufficient.
        if (snapshotId && String(snapJson.frontend_payload?.plot_id || "") !== plotId) {
          return NextResponse.json({
            available: false, reason: "requested_snapshot_plot_mismatch", snapshotId,
          }, { status: 409 });
        }
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
        if (validationState !== "valid") {
          return NextResponse.json({
            available: false,
            reason: snapshotId ? "requested_snapshot_contract_invalid" : "canonical_head_schema_stale",
            status: "stale",
            refreshRequired: !snapshotId,
            validation,
            contract_validation: snapJson.contract_validation || {},
            plotId,
            ...(snapshotId ? { snapshotId } : {}),
          }, { status: snapshotId ? 409 : 200 });
        }

        const payload = snapJson.frontend_payload || {};

        // 1. Authoritative identity from trusted backend publication snapshot envelope
        const tenant_id = snapJson.tenant_id || tenantId;
        const farm_id = snapJson.farm_id || authorizedPlot.farmId;
        const plot_id = snapJson.plot_id || plotId;
        const geometry_hash = snapJson.geometry_hash || "";
        const intelligence_snapshot_id = snapJson.snapshot_id || payload.intelligence_snapshot_id || "";
        const canonical_publication_receipt_hash = snapJson.publication_receipt_hash || payload.canonical_publication_receipt_hash || "";
        const canonical_publication_job_id = snapJson.publication_job_id || payload.canonical_publication_job_id || snapJson.job_id || "";
        const publication_id = payload.publication_id || snapJson.frontend_publication_hash || canonical_publication_receipt_hash;

        // 2. Authoritative temporal identity resolved at publication time without synthetic metadata
        const published_at = snapJson.published_at || payload.published_at || payload.publishedAt || snapJson.recorded_at;
        const evidence_cutoff_at = snapJson.evidence_cutoff_at || payload.evidence_cutoff_at || payload.evidenceCutoffAt;

        let observation_window = snapJson.observation_window || payload.observation_window || payload.observationWindow;
        if (!observation_window && Array.isArray(payload.source_window) && payload.source_window.length >= 2 && payload.source_window[0] && payload.source_window[1]) {
          observation_window = {
            start: payload.source_window[0],
            end: payload.source_window[1],
          };
        }

        // Bridge validates and transfers authoritative publication envelope without synthesis
        if (!published_at || !evidence_cutoff_at || !observation_window?.start || !observation_window?.end) {
          return NextResponse.json(
            {
              available: false,
              reason: "publication_identity_temporal_envelope_missing",
              error: "Canonical publication envelope missing authoritative published_at, evidence_cutoff_at, or observation_window",
            },
            { status: 422 }
          );
        }

        return NextResponse.json({
          ...payload,
          tenant_id,
          tenantId: tenant_id,
          farm_id,
          farmId: farm_id,
          plot_id,
          plotId: plot_id,
          geometry_hash,
          geometryHash: geometry_hash,
          publication_id,
          publicationId: publication_id,
          publication_run_id: canonical_publication_job_id,
          run_id: canonical_publication_job_id,
          runId: canonical_publication_job_id,
          intelligence_snapshot_id,
          snapshot_id: intelligence_snapshot_id,
          snapshotId: intelligence_snapshot_id,
          surface_inventory_hash: payload.surface_inventory_hash || snapJson.surface_inventory_hash || "",
          canonical_publication_receipt_hash,
          publication_receipt_hash: canonical_publication_receipt_hash,
          receiptHash: canonical_publication_receipt_hash,
          canonical_publication_job_id,
          job_id: canonical_publication_job_id,
          published_at,
          publishedAt: published_at,
          evidence_cutoff_at,
          evidenceCutoffAt: evidence_cutoff_at,
          observation_window,
          observationWindow: observation_window,
          status: "fresh",
          capturedAt: snapJson.recorded_at || snapJson.timestamp || published_at,
          surfaceDigest: snapJson.node_hash || snapJson.snapshot_id,
          surfaceGrids: payload.surfaces || payload.surface_pack || [],
          zones: payload.zones || [],
          histograms: payload.histograms || {},
          validation,
        });
      }
    }
    if (snapshotId) {
      return NextResponse.json({
        available: false, reason: "requested_snapshot_missing_publication", snapshotId,
      }, { status: 409 });
    }
  } catch (err) {
    console.warn("[Surfaces Latest] Failed to fetch canonical snapshot:", err);
    if (snapshotId) {
      return NextResponse.json({
        available: false, reason: "requested_snapshot_fetch_failed", snapshotId,
      }, { status: 503 });
    }
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
