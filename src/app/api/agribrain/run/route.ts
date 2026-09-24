/**
 * /api/agribrain/run — Unified AgriBrain Run API
 * 
 * Single entry point that replaces:
 *   - /api/agribrain/analyze (legacy orchestrator.py)
 *   - /api/agribrain/surfaces (synthetic L10 bridge)
 *   - /api/agribrain/chat (already on Orchestrator v2)
 * 
 * All modes go through Orchestrator v2 → real data only.
 * 
 * Modes:
 *   chat     — Intent-aware, returns ChatPayload (backward compat)
 *   full     — Full pipeline, returns AgriBrainRun JSON
 *   surfaces — Pipeline + Layer 10 surfaces
 */
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import {
  PUBLICATION_STATUS,
  RENDER_AUTHORIZATION_VERSION,
  SURFACES_SCHEMA_VERSION,
  inspectSurfacePublication,
} from "@/lib/agribrain/surface-contract";
import { resolveSourcePolicyDisplay } from "@/lib/agribrain/source-policy-display-resolver";
import { getSession } from "@/lib/session";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import * as crypto from "crypto";
import { getPlotRepresentativePoint, isValidWgs84Point } from "@/lib/agribrain/plot-geometry";
import {
  buildCanonicalCropCycleContextV2,
  canonicalScientificHash,
} from "@/lib/agribrain/crop-cycle-context.mjs";
import { activeCropCyclePrismaFilter } from "@/lib/agribrain/crop-cycle-status.mjs";

export type RunOutcome =
  | {
      kind: "success";
      httpStatus: 200;
      runId: string;
      scientificRequestId?: string;
      payload: any;
    }
  | {
      kind: "completed_degraded";
      httpStatus: 200;
      runId: string;
      scientificRequestId?: string;
      payload: any;
    }
  | {
      kind: "validation_error";
      httpStatus: 400;
      runId: string;
      errorCode: string;
      message: string;
      payload: any;
    }
  | {
      kind: "upstream_error";
      httpStatus: 502 | 503 | 504;
      runId: string;
      errorCode: string;
      message: string;
      payload: any;
    }
  | {
      kind: "invalid_result" | "publication_error" | "internal_error";
      httpStatus: 500;
      runId: string;
      errorCode: string;
      message: string;
      payload: any;
    };

declare global {
  var __agribrain_evidence_inflight__: Map<string, Promise<any>> | undefined;
  var __agribrain_scientific_inflight__: Map<string, Promise<RunOutcome>> | undefined;
  var __agribrain_run_inflight__: Map<string, Promise<RunOutcome>> | undefined;
}

const evidenceInflight = globalThis.__agribrain_evidence_inflight__ ?? new Map<string, Promise<any>>();
const scientificInflight = globalThis.__agribrain_scientific_inflight__ ?? new Map<string, Promise<RunOutcome>>();
const runInflight = globalThis.__agribrain_run_inflight__ ?? new Map<string, Promise<RunOutcome>>();

if (process.env.NODE_ENV !== "production") {
  globalThis.__agribrain_evidence_inflight__ = evidenceInflight;
  globalThis.__agribrain_scientific_inflight__ = scientificInflight;
  globalThis.__agribrain_run_inflight__ = runInflight;
}

function isValidSurfacePayload(payload: any): boolean {
  return inspectSurfacePublication(payload).valid;
}

function isCacheableSurfacePayload(payload: unknown): boolean {
  const candidate = payload as { surfaces?: unknown } | null;
  return Boolean(
    isValidSurfacePayload(payload) &&
    candidate &&
    Array.isArray(candidate.surfaces) &&
    candidate.surfaces.length > 0
  );
}

function getUpstreamErrorMessage(rawBody: string, fallback: string): string {
  try {
    const parsed = JSON.parse(rawBody);
    const detail = parsed?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (typeof parsed?.error === "string" && parsed.error.trim()) return parsed.error;
    if (detail && typeof detail?.error === "string" && detail.error.trim()) return detail.error;
  } catch {
    if (rawBody.trim()) return rawBody.trim().slice(0, 500);
  }
  return fallback;
}

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

function getPlotCenter(geoJson: any) {
  return getPlotRepresentativePoint(geoJson);
}

function getFarmCenter(farm: any) {
  const point = { lat: Number(farm?.latitude), lng: Number(farm?.longitude) };
  return isValidWgs84Point(point) ? point : null;
}

interface RunRequest {
  plotId: string;
  query?: string;
  mode?: "chat" | "full" | "surfaces";
  history?: Array<{ role: string; content: string }>;
  experienceLevel?: string;
  userMode?: string;
  forceRefresh?: boolean;
  experimental1m?: boolean;
  visualIntensity?: number;
  sourcePolicy?: string;
}

function publicRunResponse(outcome: RunOutcome, mode: RunRequest["mode"]) {
  if (mode !== "surfaces" || outcome.httpStatus !== 200) {
    return outcome.payload;
  }
  const raw = outcome.payload?.data ?? outcome.payload ?? {};
  const plotState = raw.source_policy_display_state?.asmaePlotState ?? {};
  return {
    success: true,
    status: "publication_pending",
    runId: outcome.runId,
    scientificRequestId: outcome.scientificRequestId,
    job: {
      id: plotState.activeSpatialJobId ?? raw.job_id ?? null,
      status: plotState.activeSpatialJobStatus ?? raw.status ?? "accepted",
      stage: plotState.activeSpatialJobStage ?? null,
      progressPct: plotState.activeSpatialJobProgressPct ?? null,
    },
    publication: {
      required: true,
      endpoint: "/api/agribrain/surfaces/latest",
    },
  };
}

function buildCanonicalExecutionKey(
  plotId: string,
  farmId: string,
  body: RunRequest
): string {
  const reqVisualIntensity = body.visualIntensity ?? 0.40;
  const modeKey = body.mode || "surfaces";
  const queryDigest = body.query
    ? crypto.createHash("sha256").update(body.query.trim()).digest("hex").slice(0, 16)
    : "empty_query";

  const canonicalObj = {
    plotId,
    farmId,
    mode: modeKey,
    // Source policy selects a display view over one canonical inventory.  It
    // must not create a different scientific execution identity.
    sourcePolicy: "canonical",
    visualIntensity: reqVisualIntensity,
    experimental1m: Boolean(body.experimental1m),
    forceRefresh: Boolean(body.forceRefresh),
    userMode: body.userMode || "farmer",
    schemaVersion: SURFACES_SCHEMA_VERSION,
    queryDigest,
  };

  const canonicalJson = JSON.stringify(canonicalObj, Object.keys(canonicalObj).sort());
  const hash = crypto.createHash("sha256").update(canonicalJson).digest("hex").slice(0, 24);
  return `run:${plotId}:${modeKey}:${hash}`;
}

async function executeRun(
  body: RunRequest,
  authorizedPlot: { id: string; farmId: string },
  requestUserId: string,
  lockKey: string
): Promise<RunOutcome> {
  const runId = `run-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  try {
    const { plotId, query, mode = "chat", history, experienceLevel, userMode = "farmer" } = body;

    // 1. Fetch real data from DB
    const plot = await prisma.plot.findFirst({
      where: {
        id: plotId,
        farm: { userId: requestUserId },
      },
      include: {
        farm: true,
        cropCycles: {
          where: { status: activeCropCyclePrismaFilter() },
          // Unknown planting dates are valid. Select the most recently
          // maintained active cycle instead of letting nullable plant dates
          // decide cycle identity.
          orderBy: { updatedAt: "desc" },
          take: 1,
          select: {
            id: true,
            cropCode: true,
            variety: true,
            plantDate: true,
            plantDateStatus: true,
            plantDateSource: true,
            plantDateConfidence: true,
            plantDateMin: true,
            plantDateMax: true,
            declaredCropAuthority: true,
            declaredCropAt: true,
            declaredCropSource: true,
            expectedHarvest: true,
            actualHarvest: true,
            status: true,
            updatedAt: true,
            tasks: { select: { id: true } },
            inputs: { select: { id: true } },
            observations: { select: { id: true } },
          },
        },
        soilAnalyses: {
          orderBy: { date: "desc" },
          take: 1,
        },
        sensors: {
          where: { status: "ACTIVE" },
          include: {
            readings: {
              orderBy: { timestamp: "desc" },
              take: 1,
            },
          },
        },
      },
    });

    const center = getPlotCenter(plot?.geoJson) || getFarmCenter(plot?.farm);
    if (!center) {
      return {
        kind: "validation_error",
        httpStatus: 400,
        runId,
        errorCode: "missing_plot_geometry_or_coordinates",
        message: "Missing plot geometry or coordinates",
        payload: { success: false, error: "missing_plot_geometry_or_coordinates" },
      };
    }

    const geometryVersion = plot?.geoJson
      ? `sha256:${canonicalScientificHash(plot.geoJson)}`
      : "unavailable";
    const irrigationType = String(
      plot?.irrigation || plot?.farm?.irrigationType || "unknown",
    ).toLowerCase();
    const context: Record<string, unknown> = {
      tenant_id: requestUserId,
      farm_id: authorizedPlot.farmId,
      plot_id: authorizedPlot.id,
      geometry_hash: geometryVersion,
      lat: center.lat,
      lng: center.lng,
      area: plot?.area,
      polygon: plot?.geoJson || null,
      field_geometry: plot?.geoJson || null,
      irrigation_type: irrigationType,
    };

    if (plot?.cropCycles?.length) {
      const activeCycle = plot.cropCycles[0];
      const storedPlantDateStatus = String(
        activeCycle.plantDateStatus || "unknown",
      ).toLowerCase();
      const plantDateStatus = (
        ["confirmed", "estimated"].includes(storedPlantDateStatus)
        && activeCycle.plantDate
      ) || (
        storedPlantDateStatus === "interval"
        && activeCycle.plantDateMin
        && activeCycle.plantDateMax
      )
        ? storedPlantDateStatus
        : "unknown";
      const plantDate = plantDateStatus === "unknown"
        ? null
        : activeCycle.plantDate?.toISOString() || null;
      const plantDateMin = plantDateStatus === "unknown"
        ? null
        : activeCycle.plantDateMin?.toISOString() || plantDate;
      const plantDateMax = plantDateStatus === "unknown"
        ? null
        : activeCycle.plantDateMax?.toISOString() || plantDate;
      const rawPlantDateConfidence = Number(activeCycle.plantDateConfidence);
      const plantDateConfidence = Number.isFinite(rawPlantDateConfidence)
        && rawPlantDateConfidence >= 0
        && rawPlantDateConfidence <= 1
        ? rawPlantDateConfidence
        : null;
      const storedDeclaredCropAuthority = String(
        activeCycle.declaredCropAuthority || "REGISTRY_DECLARED",
      ).toUpperCase();
      const declaredCropAuthority = [
        "UNKNOWN",
        "REGISTRY_DECLARED",
        "USER_CONFIRMED",
        "FARMER_CONFIRMED",
        "OFFICIAL_PARCEL_LABEL",
        "AGRONOMIST_CONFIRMED",
      ].includes(storedDeclaredCropAuthority)
        ? storedDeclaredCropAuthority
        : "REGISTRY_DECLARED";
      // A database update time is not evidence of when crop identity was
      // declared. Legacy cycles keep this unknown until an authenticated
      // declaration writes the dedicated field.
      const declaredCropAt = activeCycle.declaredCropAt?.toISOString() || null;
      const declaredCropSource = String(
        activeCycle.declaredCropSource || "unknown",
      ).trim() || "unknown";
      const managementEventRefs = [
        ...activeCycle.tasks.map((item) => `task:${item.id}`),
        ...activeCycle.inputs.map((item) => `input:${item.id}`),
        ...activeCycle.observations.map((item) => `observation:${item.id}`),
      ];
      const cropCycleContext = buildCanonicalCropCycleContextV2({
        plot_namespace: {
          tenant_id: requestUserId,
          farm_id: authorizedPlot.farmId,
          plot_id: authorizedPlot.id,
        },
        crop_cycle_id: activeCycle.id,
        geometry_version: geometryVersion,
        effective_at: activeCycle.updatedAt.toISOString(),
        declared_crop_code: activeCycle.cropCode,
        declared_crop_authority: declaredCropAuthority,
        declared_crop_at: declaredCropAt,
        declared_crop_source: declaredCropSource,
        variety: activeCycle.variety,
        irrigation_type: irrigationType,
        plant_date: {
          status: plantDateStatus,
          source: plantDateStatus === "unknown"
            ? "unknown"
            : activeCycle.plantDateSource || "unknown",
          confidence: plantDateConfidence,
          nominal: plantDate,
          range_start: plantDateMin,
          range_end: plantDateMax,
        },
        harvest_dates: {
          expected: activeCycle.expectedHarvest?.toISOString() || null,
          actual: activeCycle.actualHarvest?.toISOString() || null,
        },
        administrative_status: activeCycle.status,
        management_event_refs: managementEventRefs,
      });
      context.crop = activeCycle.cropCode;
      context.crop_cycle_id = activeCycle.id;
      context.crop_season_id = activeCycle.id;
      context.plant_date = plantDate;
      context.planting_date = plantDate;
      context.plant_date_status = plantDateStatus;
      context.plant_date_source = plantDateStatus === "unknown"
        ? "unknown"
        : activeCycle.plantDateSource || "unknown";
      context.plant_date_confidence = plantDateConfidence;
      context.plant_date_min = plantDateMin;
      context.plant_date_max = plantDateMax;
      context.crop_cycle_effective_at = activeCycle.updatedAt.toISOString();
      context.declared_crop_authority = declaredCropAuthority;
      context.declared_crop_at = declaredCropAt;
      context.declared_crop_source = declaredCropSource;
      context.administrative_status = activeCycle.status;
      context.crop_cycle_context = cropCycleContext;
    }

    if (plot?.soilAnalyses?.length) {
      const soil = plot.soilAnalyses[0];
      context.soil_type = plot.soilType || "LOAM";
      context.soil = {
        type: plot.soilType || "LOAM",
        ph: soil.ph,
        organic_matter: soil.organicMatter,
        texture: soil.texture,
      };
    }

    if (plot?.sensors?.length) {
      const sensorArray = plot.sensors
        .filter((s: any) => s.readings.length > 0)
        .map((s: any) => {
          const r = s.readings[0];
          return {
            id: s.id,
            deviceId: s.deviceId,
            type: s.type,
            lastSync: s.lastSync?.toISOString() || new Date().toISOString(),
            soilMoisture: r.soilMoisture != null ? Number(r.soilMoisture) : null,
            temperature: r.temperature != null ? Number(r.temperature) : null,
            humidity: r.humidity != null ? Number(r.humidity) : null,
            rainfall: r.rainfall != null ? Number(r.rainfall) : null,
            ec: r.ec != null ? Number(r.ec) : null,
            windSpeed: r.windSpeed != null ? Number(r.windSpeed) : null,
            battery: r.battery != null ? Number(r.battery) : null,
            rssi: r.rssi != null ? Number(r.rssi) : null,
          };
        });

      const sensorSummary: Record<string, number> = {};
      const moistureValues: number[] = [];
      for (const s of sensorArray) {
        if (s.soilMoisture != null) moistureValues.push(s.soilMoisture);
        if (s.temperature != null) sensorSummary.temperature = s.temperature;
        if (s.humidity != null) sensorSummary.humidity = s.humidity;
        if (s.rainfall != null) sensorSummary.rainfall = s.rainfall;
        if (s.ec != null) sensorSummary.ec = s.ec;
        if (s.windSpeed != null) sensorSummary.wind_speed = s.windSpeed;
      }
      if (moistureValues.length > 0) {
        sensorSummary.soil_moisture = moistureValues.reduce((a, b) => a + b, 0) / moistureValues.length;
      }

      context.sensors = sensorArray;
      context.sensor_summary = sensorSummary;
    }

    const contextB64 = Buffer.from(JSON.stringify(context)).toString("base64");
    const historyB64 = history && history.length > 0
      ? Buffer.from(JSON.stringify(history)).toString("base64")
      : "";

    let requestedSourcePolicy = body.sourcePolicy || "satellite";
    if (requestedSourcePolicy === "asmae") {
      requestedSourcePolicy = "asmae_diagnostic";
    }

    const payload = {
      context: contextB64,
      query: query || "",
      mode: mode || "chat",
      history: historyB64,
      exp: experienceLevel || "INTERMEDIATE",
      userMode: userMode,
      force_refresh: body.forceRefresh || false,
      experimental_1m: body.experimental1m || false,
      visual_intensity: body.visualIntensity ?? 0.40,
      source_policy: "canonical",
      run_id: runId,
    };

    const bodyText = JSON.stringify(payload);
    const { buildSignedInternalHeaders } = await import("@/lib/agribrain/internal-service-auth");
    const signedHeaders = buildSignedInternalHeaders(
      "POST",
      "/v2/run",
      {
        tenantId: requestUserId,
        farmId: authorizedPlot.farmId,
        plotId: authorizedPlot.id,
      },
      bodyText
    );

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
    const timeoutMs = 360_000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    let response: Response;
    try {
      response = await fetch(`${apiUrl}/v2/run`, {
        method: "POST",
        headers: {
          ...signedHeaders,
          "Content-Type": "application/json",
        },
        body: bodyText,
        signal: controller.signal,
      });

    } catch (fetchErr: any) {
      if (fetchErr.name === "AbortError") {
        return {
          kind: "upstream_error",
          httpStatus: 504,
          runId,
          errorCode: "agribrain_pipeline_timeout",
          message: "AgriBrain pipeline timed out — try again",
          payload: { success: false, error: "AgriBrain pipeline timed out — try again" },
        };
      }
      return {
        kind: "upstream_error",
        httpStatus: 503,
        runId,
        errorCode: "agribrain_service_unreachable",
        message: fetchErr.message || "AgriBrain service unreachable",
        payload: { success: false, error: `AgriBrain service unreachable: ${fetchErr.message}` },
      };
    } finally {
      clearTimeout(timeoutId);
    }

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[AgriBrain Run API] Upstream error ${response.status}: ${errorText}`);
      const upstreamMessage = getUpstreamErrorMessage(errorText, response.statusText);
      const httpStatus = (response.status >= 500 && response.status <= 504) ? (response.status as 502 | 503 | 504) : 503;
      return {
        kind: "upstream_error",
        httpStatus,
        runId,
        errorCode: "upstream_run_failed",
        message: upstreamMessage,
        payload: { success: false, error: `AgriBrain run failed: ${upstreamMessage}` },
      };
    }

    const result = await response.json();

    if (result.error) {
      return {
        kind: "invalid_result",
        httpStatus: 500,
        runId,
        errorCode: result.type || "pipeline_result_error",
        message: result.error,
        payload: { success: false, error: result.error, details: result.type },
      };
    }

    const l10Data = result.data ?? result;
    const publicationInspection = inspectSurfacePublication(l10Data);
    if (mode === "surfaces" && !publicationInspection.valid) {
      return {
        kind: "publication_error",
        httpStatus: 500,
        runId,
        errorCode: publicationInspection.status,
        message: `Layer 10 publication rejected: ${publicationInspection.reason}`,
        payload: {
          success: false,
          error: `Layer 10 publication rejected: ${publicationInspection.reason}`,
          publication_status: publicationInspection.status,
          publication_reason: publicationInspection.reason,
          request_run_id: runId,
        },
      };
    }
    if (mode === "surfaces" && isCacheableSurfacePayload(l10Data)) {
      try {
        const { extractSurfaceStats, computeSurfaceContractDigest } = await import("@/lib/ml-features");
        const { gzipSync } = await import("zlib");

        const surfaceStats = extractSurfaceStats(l10Data);
        const surfaceDigest = await computeSurfaceContractDigest(l10Data);

        let latestSnap = await prisma.intelligenceSnapshot.findFirst({
          where: { plotId, farmId: authorizedPlot.farmId },
          orderBy: { capturedAt: "desc" },
          select: { id: true, surfaceDigest: true, surfaceGridsByPolicy: true, surfaceDigestByPolicy: true },
        });

        const canonicalInventoryKey = "canonical";
        const requestedVisualIntensity = l10Data.provenance?.visual_intensity ?? 0.40;

        let snapId: string | null = latestSnap ? latestSnap.id : null;
        let existingGrids = latestSnap ? ((latestSnap.surfaceGridsByPolicy as Record<string, any>) || {}) : {};
        let existingDigests = latestSnap ? ((latestSnap.surfaceDigestByPolicy as Record<string, string>) || {}) : {};

        if (!latestSnap) {
          const newSnap = await prisma.intelligenceSnapshot.create({
            data: {
              plotId,
              farmId: authorizedPlot.farmId,
              lat: center.lat,
              lng: center.lng,
              engines: [],
              timeline: { weather: [], ndvi: [], sar: [], waterBalance: [], forecast: [], dateRange: { from: "", to: "", today: "" } },
              current: { weather: null, indices: null, soil: null, waterBalance: null },
              assimilation: { dataAge_days: 0, sources_used: [], sources_count: 0, freshness_score: 0, assimilated: false, raw_available: false },
              mlFeatures: {},
              surfaceStats: surfaceStats as any,
              surfaceDigest,
              surfaceGridsByPolicy: {},
              surfaceDigestByPolicy: {},
              expiresAt: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000),
            },
          });
          snapId = newSnap.id;
          latestSnap = newSnap as any;
        }

        if (latestSnap && snapId) {
          const existingEntry = existingGrids[canonicalInventoryKey];
          const policyEntryInvalid =
            !existingEntry ||
            existingEntry.schemaVersion !== SURFACES_SCHEMA_VERSION ||
            existingEntry.experimentalVisualLadder === undefined ||
            !existingEntry.asmaeEvidenceState ||
            !existingEntry.sourcePolicyDisplayState ||
            !existingEntry.surfaceInventory ||
            !existingEntry.displayStateByPolicyAndMode ||
            existingEntry.surfaceDigest !== surfaceDigest ||
            existingEntry.inventoryPolicy !== canonicalInventoryKey ||
            Math.abs((existingEntry.visualIntensity ?? 0.4) - requestedVisualIntensity) > 0.01 ||
            existingEntry.render_authorization_version !== RENDER_AUTHORIZATION_VERSION ||
            existingEntry.publicationStatus !== l10Data.publication_status ||
            existingEntry.publicationId !== l10Data.publication_id ||
            existingEntry.publicationRunId !== l10Data.publication_run_id ||
            !existingEntry.render_authorizations ||
            !existingEntry.asmae_proof ||
            Object.keys(existingEntry.asmae_proof).length === 0;

          const gridsChanged = surfaceDigest !== latestSnap.surfaceDigest;

          if ((gridsChanged || policyEntryInvalid) && Array.isArray(l10Data.surfaces)) {
            const displayStateByPolicyAndMode: Record<string, Record<string, string | null>> = {};
            const policies = ["satellite", "experimental", "asmae_diagnostic", "hybrid"];
            const modes = ["canopy", "water", "nutrients", "salinity", "risk", "veg_attention", "uncertainty", "resolution_coverage"];
            for (const p of policies) {
              displayStateByPolicyAndMode[p] = {};
              for (const m of modes) {
                const resolved = resolveSourcePolicyDisplay({
                  surfaces: l10Data.surfaces || [],
                  requestedPolicy: p,
                  activeMode: m,
                  sourcePolicyDisplayState: l10Data.source_policy_display_state,
                  asmaeEvidenceState: l10Data.asmae_evidence_state,
                  experimentalVisualLadder: l10Data.source_policy_display_state?.experimentalVisualLadder,
                  showExperimental1m: p === "experimental" || p === "hybrid",
                  asmae_proof: (l10Data.asmae_proof && Object.keys(l10Data.asmae_proof).length > 0) ? l10Data.asmae_proof : buildDefaultAsmaeProof(),
                  renderAuthorizations: l10Data.render_authorizations,
                });
                displayStateByPolicyAndMode[p][m] = resolved.activeSurfaceType;
              }
            }

            const gridData = {
              version: SURFACES_SCHEMA_VERSION,
              schema_version: SURFACES_SCHEMA_VERSION,
              plot_id: plotId,
              run_id: l10Data.run_id,
              publication_run_id: l10Data.publication_run_id,
              request_run_id: l10Data.request_run_id || runId,
              publication_id: l10Data.publication_id,
              publication_status: l10Data.publication_status,
              generated_at: l10Data.generated_at || l10Data.timestamp || l10Data.provenance?.generated_at,
              source_policy: canonicalInventoryKey,
              requested_source_policy_at_publication: requestedSourcePolicy,
              surface_policy_version: process.env.RENDER_POLICY_VERSION || "v1",
              visual_intensity: l10Data.provenance?.visual_intensity ?? 0.40,
              asmae_enabled: (process.env.ASMAE_ENABLED || "false").toLowerCase(),
              l10_asmae_surfaces_enabled: (process.env.L10_ASMAE_SURFACES_ENABLED || "false").toLowerCase(),
              l10_asmae_diagnostic_aliases_enabled: (process.env.L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED || "false").toLowerCase(),
              surface_ladder_policy_version: process.env.SURFACE_LADDER_POLICY_VERSION || "v1",
              render_policy_version: process.env.RENDER_POLICY_VERSION || "v1",
              mode_surface_plan_version: process.env.MODE_SURFACE_PLAN_VERSION || "v1",
              display_grid_policy_version: process.env.DISPLAY_GRID_POLICY_VERSION || "v1",
              mode_surface_plan: l10Data.mode_surface_plan || {},
              mode_display_state: l10Data.mode_display_state || {},
              surface_inventory: l10Data.surface_inventory || {},
              source_policy_display_state: l10Data.source_policy_display_state || {},
              asmae_evidence_state: l10Data.asmae_evidence_state || {},
              core_asmae_evidence_state: l10Data.core_asmae_evidence_state || l10Data.asmae_evidence_state || {},
              publication_surface_state: l10Data.publication_surface_state || {},
              publication_demotion: l10Data.publication_demotion || {},
              asmae_feature_pack: l10Data.asmae_feature_pack || {},
              experimentalVisualLadder: l10Data.source_policy_display_state?.experimentalVisualLadder || null,
              asmaeApprovalLadder: l10Data.source_policy_display_state?.asmaeApprovalLadder || null,
              displayStateByPolicyAndMode,
              surface_behavior_proof: l10Data.surface_behavior_proof || {},
              display_trace: l10Data.display_trace || {},
              asmae_proof: (l10Data.asmae_proof && Object.keys(l10Data.asmae_proof).length > 0) ? l10Data.asmae_proof : buildDefaultAsmaeProof(),
              render_authorizations: l10Data.render_authorizations || {},
              render_authorization_version: l10Data.render_authorization_version || "",
              intelligence_snapshot_id: l10Data.intelligence_snapshot_id || snapId,
              agribrain_run_id: l10Data.agribrain_run_id || l10Data.run_id || "",
              source_window: l10Data.source_window || [],
              surface_schema_version: l10Data.surface_schema_version || SURFACES_SCHEMA_VERSION,
              temporal_evidence_contract_version: l10Data.temporal_evidence_contract_version || "temporal_evidence_admission_v1",
              layer_results: l10Data.layer_results || {},
              global_quality: l10Data.global_quality || {},
              rendering_quality: l10Data.quality || {},
              scientific_pipeline_quality: l10Data.global_quality || {},
              surfaces: l10Data.surfaces.map((s: any) => {
                const surfaceType = s.semantic_type || s.type;
                return {
                  ...s,
                  type: surfaceType,
                  semantic_type: surfaceType,
                  values: s.values,
                  width: s.values?.[0]?.length || s.width || 0,
                  height: s.values?.length || s.height || 0,
                  grid_spec: s.grid_spec || null,
                  display_grid_spec: s.display_grid_spec || null,
                  source_grid_spec: s.source_grid_spec || null,
                  provenance: s.provenance || {},
                  render_kind: s.render_kind || s.renderKind || null,
                  display_level: s.display_level || s.displayLevel || null,
                  source_reality: s.source_reality ?? s.provenance?.source_reality ?? null,
                  diagnostic_only: s.diagnostic_only ?? s.provenance?.diagnostic_only ?? null,
                  state_update_allowed: s.state_update_allowed ?? s.provenance?.state_update_allowed ?? null,
                  prescription_driver_allowed: s.prescription_driver_allowed ?? s.provenance?.prescription_driver_allowed ?? null,
                  confidence: s.confidence ?? s.provenance?.confidence ?? null,
                  uncertainty: s.uncertainty ?? s.provenance?.uncertainty ?? null,
                  authority_block_reason: s.authority_block_reason ?? s.provenance?.authority_block_reason ?? null,
                };
              }),
              zones: l10Data.zones || [],
              histograms: l10Data.histograms || {},
              quality: l10Data.quality || {},
              fallback_guidance: l10Data.fallback_guidance || {},
              explainability_pack: l10Data.explainability_pack || {},
              ground_truth_summary: l10Data.ground_truth_summary || undefined,
              visual_source: l10Data.visual_source || undefined,
            };
            const compressed = gzipSync(Buffer.from(JSON.stringify(gridData)));
            const resolvedPolicy = "canonical";
            
            const existingGridsUpdated = { ...existingGrids };
            const existingDigestsUpdated = { ...(existingDigests as Record<string, string> || {}) };
            
            existingGridsUpdated[canonicalInventoryKey] = {
              gz: compressed.toString("base64"),
              inventoryPolicy: canonicalInventoryKey,
              resolvedPolicy,
              surfaceDigest,
              visualIntensity: requestedVisualIntensity,
              sourcePolicyDisplayState: l10Data.source_policy_display_state || {},
              asmaeEvidenceState: l10Data.asmae_evidence_state || {},
              coreAsmaeEvidenceState: l10Data.core_asmae_evidence_state || l10Data.asmae_evidence_state || {},
              publicationSurfaceState: l10Data.publication_surface_state || {},
              publicationDemotion: l10Data.publication_demotion || {},
              asmaeFeaturePack: l10Data.asmae_feature_pack || {},
              experimentalVisualLadder: l10Data.source_policy_display_state?.experimentalVisualLadder || null,
              asmaeApprovalLadder: l10Data.source_policy_display_state?.asmaeApprovalLadder || null,
              surfaceInventory: l10Data.surface_inventory || {},
              displayStateByPolicyAndMode,
              schemaVersion: SURFACES_SCHEMA_VERSION,
              createdAt: new Date().toISOString(),
              publicationStatus: l10Data.publication_status,
              publicationId: l10Data.publication_id,
              publicationRunId: l10Data.publication_run_id,
              surface_behavior_proof: l10Data.surface_behavior_proof || {},
              display_trace: l10Data.display_trace || {},
              asmae_proof: l10Data.asmae_proof || {},
              asmae_feature_pack: l10Data.asmae_feature_pack || {},
              render_authorizations: l10Data.render_authorizations || {},
              render_authorization_version: l10Data.render_authorization_version || "",
              intelligence_snapshot_id: l10Data.intelligence_snapshot_id || snapId,
              agribrain_run_id: l10Data.agribrain_run_id || l10Data.run_id || "",
            };
            existingDigestsUpdated[canonicalInventoryKey] = surfaceDigest;

            await prisma.intelligenceSnapshot.update({
              where: { id: snapId },
              data: {
                capturedAt: new Date(),
                surfaceStats: surfaceStats as any,
                surfaceDigest,
                surfaceGridsByPolicy: existingGridsUpdated,
                surfaceDigestByPolicy: existingDigestsUpdated,
              } as any,
            });
            console.log(`[AgriBrain Run] Updated snapshot ${snapId} with canonical L10 surface inventory`);
          }
        }
      } catch (surfaceErr) {
        console.warn("[AgriBrain Run] Failed to update surface stats:", surfaceErr);
      }
    }

    const isDegraded =
      mode === "surfaces"
        ? publicationInspection.status === PUBLICATION_STATUS.VALID_DEGRADED
        : l10Data.status === "degraded" || l10Data.placeholder_only === true;
    return {
      kind: isDegraded ? "completed_degraded" : "success",
      httpStatus: 200,
      runId,
      scientificRequestId: lockKey,
      payload: result,
    };
  } catch (error: any) {
    console.error("[AgriBrain Run] Internal Exception:", error);
    return {
      kind: "internal_error",
      httpStatus: 500,
      runId,
      errorCode: "internal_exception",
      message: error.message || "Internal AgriBrain exception",
      payload: { success: false, error: `AgriBrain run failed: ${error.message || "Internal exception"}` },
    };
  }
}

export async function POST(request: NextRequest) {
  try {
    const body: RunRequest = await request.json();
    const { plotId } = body;

    if (!plotId) {
      return NextResponse.json(
        { success: false, error: "plotId is required" },
        { status: 400 }
      );
    }

    const access = await authorizePlot(plotId);
    if (access.status !== 200 || !access.plot) {
      return NextResponse.json(
        { success: false, error: access.status === 401 ? "Authentication required" : "Plot not found" },
        { status: access.status }
      );
    }
    const authorizedPlot = access.plot;
    const requestUserId = authorizedPlot.farm?.userId || access.userId!;

    const lockKey = buildCanonicalExecutionKey(plotId, authorizedPlot.farmId, body);

    const existingPromise = runInflight.get(lockKey);
    if (existingPromise) {
      console.log(`[AgriBrain Singleflight] Reusing active run promise for key: ${lockKey}`);
      const outcome = await existingPromise;
      return NextResponse.json(publicRunResponse(outcome, body.mode), { status: outcome.httpStatus });
    }

    const executionPromise = executeRun(body, authorizedPlot, requestUserId, lockKey);
    runInflight.set(lockKey, executionPromise);

    try {
      const outcome = await executionPromise;
      return NextResponse.json(publicRunResponse(outcome, body.mode), { status: outcome.httpStatus });
    } finally {
      if (runInflight.get(lockKey) === executionPromise) {
        runInflight.delete(lockKey);
        console.log(`[AgriBrain Singleflight] Released singleflight lock for key: ${lockKey}`);
      }
    }
  } catch (error: any) {
    console.error("[AgriBrain Run API] Request handling error:", error);
    return NextResponse.json(
      { success: false, error: error.message || "Failed to process request" },
      { status: 500 }
    );
  }
}
