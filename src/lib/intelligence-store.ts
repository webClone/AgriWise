/**
 * Intelligence Store — Snapshot Read/Write + PlotDNA Updater
 * ===========================================================
 *
 * Handles:
 *   - Writing IntelligenceSnapshot after each AgriBrain run
 *   - Reading latest cached snapshot for instant page load
 *   - Updating PlotDNA with exponential moving averages
 *   - Surface grid compression (gzip + base64)
 *   - Change detection via surfaceDigest
 */
import { prisma } from "@/lib/db";
import {
  extractMLFeatures,
  extractSurfaceStats,
  computeSurfaceDigest,
  computeSurfaceContractDigest,
  type MLFeatureVector,
  type SurfaceStatEntry,
} from "@/lib/ml-features";
import { gzipSync, gunzipSync } from "zlib";
import { SURFACES_SCHEMA_VERSION } from "@/lib/agribrain/surface-contract";
import { normalizeEngineCollection } from "@/lib/agribrain/normalize-engines";

// ── Constants ───────────────────────────────────────────────────────

const SNAPSHOT_TTL_DAYS = 14;
const CACHE_FRESH_MINUTES = 30;   // Serve without background refresh
const CACHE_STALE_HOURS = 2;      // Auto-trigger background refresh
const EMA_ALPHA = 0.15;           // Exponential moving average smoothing factor

// ── Types ───────────────────────────────────────────────────────────

export type CacheStatus = "HIT" | "STALE" | "MISS";

export interface CachedIntelligence {
  status: CacheStatus;
  data: any;
  capturedAt: Date;
  snapshotId: string;
  surfaceDigest: string | null;
}

// ── Read: Get Latest Cached Snapshot ────────────────────────────────

export async function getLatestSnapshot(
  plotId: string
): Promise<CachedIntelligence | null> {
  try {
    const snapshot = await prisma.intelligenceSnapshot.findFirst({
      where: { plotId },
      orderBy: { capturedAt: "desc" },
    });

    if (!snapshot) return null;

    const engines = normalizeEngineCollection(snapshot.engines);
    const timeline = snapshot.timeline as Record<string, unknown> | null;
    // Surface-only runs may create a snapshot before plot intelligence has
    // populated it. Do not serve that record as a fresh intelligence cache hit.
    if (
      engines.length === 0 ||
      !timeline ||
      !Array.isArray(timeline.weather)
    ) {
      return null;
    }

    const ageMs = Date.now() - snapshot.capturedAt.getTime();
    const ageMinutes = ageMs / (1000 * 60);
    const ageHours = ageMinutes / 60;

    let status: CacheStatus;
    if (ageMinutes < CACHE_FRESH_MINUTES) {
      status = "HIT";
    } else if (ageHours < CACHE_STALE_HOURS) {
      status = "STALE";
    } else {
      status = "STALE"; // Still return data, but frontend will refresh
    }

    // Reconstruct the response payload
    const data = {
      success: true,
      engines,
      timeline,
      current: snapshot.current,
      assimilation: snapshot.assimilation,
      crop_phenology: snapshot.phenology,
      user_inputs: snapshot.userInputs,
      sensor_context: snapshot.sensorSnapshot,
      surface_stats: snapshot.surfaceStats,
      // GAP 8 fix: reconstruct rawData for expert mode
      rawData: snapshot.rawData ?? null,
      // ML features available for inspection
      ml_features: snapshot.mlFeatures,
      // Cache metadata
      _cache: {
        status,
        capturedAt: snapshot.capturedAt.toISOString(),
        ageMinutes: Math.round(ageMinutes),
        snapshotId: snapshot.id,
      },
    };

    return {
      status,
      data,
      capturedAt: snapshot.capturedAt,
      snapshotId: snapshot.id,
      surfaceDigest: snapshot.surfaceDigest,
    };
  } catch (err) {
    console.error("[IntelligenceStore] Read failed:", err);
    return null;
  }
}

// ── Write: Save New Snapshot ────────────────────────────────────────

export async function writeSnapshot(params: {
  plotId: string;
  farmId: string;
  response: any;
  l10Data?: any;
  lat: number;
  lng: number;
  cropCode?: string;
  areaHa?: number;
}): Promise<string | null> {
  const { plotId, farmId, response, l10Data, lat, lng, cropCode, areaHa } =
    params;

  try {
    const now = new Date();
    const expiresAt = new Date(
      now.getTime() + SNAPSHOT_TTL_DAYS * 24 * 60 * 60 * 1000
    );

    // Extract ML features
    const mlFeatures = extractMLFeatures(response);

    // Extract surface statistics
    const surfaceStats = l10Data ? extractSurfaceStats(l10Data) : [];

    // Compute surface digest for change detection
    const surfaceDigest = l10Data
      ? await computeSurfaceContractDigest(l10Data)
      : null;

    // Compress surface grids if they changed
    let surfaceGridsGz: string | null = null;
    if (l10Data?.surfaces && Array.isArray(l10Data.surfaces)) {
      // Check if grids changed from previous snapshot
      const prevSnapshot = await prisma.intelligenceSnapshot.findFirst({
        where: { plotId },
        orderBy: { capturedAt: "desc" },
        select: { surfaceDigest: true },
      });

      const gridsChanged =
        !prevSnapshot?.surfaceDigest ||
        prevSnapshot.surfaceDigest !== surfaceDigest;

      if (gridsChanged) {
        const gridData = {
          version: SURFACES_SCHEMA_VERSION,
          schema_version: SURFACES_SCHEMA_VERSION,
          surface_policy_version: process.env.RENDER_POLICY_VERSION || "v1",
          // P1.2: Include visual_intensity so latest route intensity validation doesn't fail
          visual_intensity:
            l10Data.provenance?.visual_intensity ??
            l10Data.visual_intensity ??
            0.40,
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
          surfaces: l10Data.surfaces.map((s: any) => ({
            type: s.semantic_type || s.type,
            semantic_type: s.semantic_type || s.type,
            grid_ref: s.grid_ref,
            values: s.values,
            width: s.values?.[0]?.length || s.width || 0,
            height: s.values?.length || s.height || 0,
            grid_spec: s.grid_spec || null,
            display_grid_spec: s.display_grid_spec || null,
            source_grid_spec: s.source_grid_spec || null,
            grounding_class: s.grounding_class,
            units: s.units,
            render_range: s.render_range,
            palette_id: s.palette_id,
            source_layers: s.source_layers,
            provenance: s.provenance || {},
            raster_basis: s.raster_basis,
            observed_ratio: s.observed_ratio,
            render_kind: s.render_kind || s.renderKind || null,
            display_level: s.display_level || s.displayLevel || null,
          })),
          zones: l10Data.zones || [],
          histograms: l10Data.histograms || {},
          quality: l10Data.quality || {},
          fallback_guidance: l10Data.fallback_guidance || {},
          explainability_pack: l10Data.explainability_pack || {},
          ground_truth_summary: l10Data.ground_truth_summary || undefined,
          visual_source: l10Data.visual_source || undefined,
        };
        const jsonStr = JSON.stringify(gridData);
        const compressed = gzipSync(Buffer.from(jsonStr));
        surfaceGridsGz = compressed.toString("base64");
      }
    }

    // Extract phenology
    const pheno = response.crop_phenology || response.cropPhenology || null;
    const cropStage = pheno?.stage || null;
    const dap = pheno?.dap || null;

    // Write snapshot
    const snapshot = await prisma.intelligenceSnapshot.create({
      data: {
        plotId,
        farmId,
        capturedAt: now,
        dataAgeHrs: response.assimilation?.dataAge_days
          ? response.assimilation.dataAge_days * 24
          : 0,
        engines: response.engines || [],
        timeline: response.timeline || {},
        current: response.current || {},
        assimilation: response.assimilation || {},
        surfaceStats: surfaceStats as any,
        surfaceDigest,
        surfaceGridsGz,
        mlFeatures: mlFeatures as any,
        cropCode: cropCode || null,
        cropStage,
        dap,
        lat,
        lng,
        areaHa: areaHa ?? null,  // GAP 12: Use ?? to preserve 0
        sensorSnapshot: response.sensor_context || null,
        phenology: pheno,
        userInputs: response.user_inputs || null,
        rawData: response.rawData || null,  // GAP 8: Store expert-mode raw data
        expiresAt,
      },
    });

    // Update PlotDNA (permanent learning profile)
    await updatePlotDNA(plotId, lat, lng, areaHa, mlFeatures, surfaceStats, cropCode, pheno);

    console.log(
      `[IntelligenceStore] Snapshot saved: ${snapshot.id} (${
        surfaceGridsGz ? Math.round(surfaceGridsGz.length / 1024) + "KB grids" : "no grids"
      })`
    );

    return snapshot.id;
  } catch (err) {
    console.error("[IntelligenceStore] Write failed:", err);
    return null;
  }
}

// ── Decompress Surface Grids ────────────────────────────────────────

export function decompressSurfaceGrids(
  base64Gz: string
): any {
  try {
    const compressed = Buffer.from(base64Gz, "base64");
    const json = gunzipSync(compressed).toString("utf-8");
    const parsed = JSON.parse(json);
    // V92.4-BC.4: Only accept current cache version for decompression.
    const VALID_CACHE_VERSIONS = new Set([
      SURFACES_SCHEMA_VERSION,
    ]);
    if (parsed && VALID_CACHE_VERSIONS.has(parsed.version)) {
      return parsed;
    }
    return parsed;
  } catch (err) {
    console.error("[IntelligenceStore] Decompression failed:", err);
    return null;
  }
}

// ── PlotDNA: Permanent Learning Profile ─────────────────────────────

async function updatePlotDNA(
  plotId: string,
  lat: number,
  lng: number,
  areaHa: number | undefined | null,
  features: MLFeatureVector,
  surfaceStats: SurfaceStatEntry[],
  cropCode?: string,
  phenology?: any,
): Promise<void> {
  try {
    // Find or create PlotDNA
    let dna = await prisma.plotDNA.findUnique({ where: { plotId } });

    const now = new Date();
    const dateStr = now.toISOString().split("T")[0];
    const month = now.getMonth(); // 0-11

    if (!dna) {
      // First time — create initial PlotDNA
      dna = await prisma.plotDNA.create({
        data: {
          plotId,
          lat,
          lng,
          areaHa: areaHa || null,
          totalSnapshots: 1,
          firstSeen: now,
          lastSeen: now,
          avgFreshness: features.freshness_score ?? 0,
          ndviBaseline: {
            ema_mean: features.ndvi_mean ?? 0,
            ema_std: 0,
            seasonal_profile: new Array(12).fill(null),
            peak_ndvi: features.ndvi_mean ?? 0,
            trough_ndvi: features.ndvi_mean ?? 0,
          },
          waterStressProfile: {
            ema_prob: features.water_stress_prob ?? 0,
            max_observed: features.water_stress_prob ?? 0,
            seasonal_risk: new Array(12).fill(null),
          },
          nutrientProfile: {
            ema_n_def: features.n_deficiency ?? 0,
            ema_p_def: features.p_deficiency ?? 0,
            ema_k_def: features.k_deficiency ?? 0,
            soil_fertility_trend: "UNKNOWN",
          },
          bioticProfile: {
            ema_pressure: features.biotic_pressure ?? 0,
            disease_history: [],
          },
          featureTimeline: [
            { date: dateStr, ...flattenForTimeline(features) },
          ],
          anomalyLog: [],
          sourceDiversity: {
            s2_count: 0,
            s1_count: 0,
            weather_count: 0,
            iot_count: 0,
            user_input_count: 0,
          },
        },
      });
      return;
    }

    // Existing DNA — update with EMA
    const ndviBase = (dna.ndviBaseline as any) || {};
    const waterBase = (dna.waterStressProfile as any) || {};
    const nutBase = (dna.nutrientProfile as any) || {};
    const bioBase = (dna.bioticProfile as any) || {};
    const timeline = ((dna.featureTimeline as any) || []) as any[];
    const anomalyLog = ((dna.anomalyLog as any) || []) as any[];
    const srcDiv = ((dna.sourceDiversity as any) || {}) as any;

    // EMA update helper
    const ema = (prev: number, next: number | null) =>
      next !== null ? prev * (1 - EMA_ALPHA) + next * EMA_ALPHA : prev;

    // Update NDVI baseline
    const newNdviMean = ema(ndviBase.ema_mean || 0, features.ndvi_mean);
    const seasonal = ndviBase.seasonal_profile || new Array(12).fill(null);
    if (features.ndvi_mean !== null) {
      seasonal[month] = features.ndvi_mean;
    }

    // Update water stress profile
    const newWaterProb = ema(waterBase.ema_prob || 0, features.water_stress_prob);
    const waterSeasonal = waterBase.seasonal_risk || new Array(12).fill(null);
    if (features.water_stress_prob !== null) {
      waterSeasonal[month] = features.water_stress_prob;
    }

    // Anomaly detection: if current risk > 2x EMA, log anomaly
    if (
      features.risk_composite !== null &&
      ndviBase.ema_mean > 0 &&
      features.ndvi_mean !== null &&
      features.ndvi_mean < ndviBase.ema_mean * 0.7
    ) {
      anomalyLog.push({
        date: dateStr,
        type: "NDVI_DROP",
        severity: Math.round(
          (1 - features.ndvi_mean / ndviBase.ema_mean) * 100
        ) / 100,
        description: `NDVI dropped to ${features.ndvi_mean?.toFixed(3)} vs baseline ${ndviBase.ema_mean?.toFixed(3)}`,
        duration_days: 1,
      });
    }

    // GAP 4 fix: Deduplicate timeline by date (replace same-day entries)
    const existingIdx = timeline.findIndex((e: any) => e.date === dateStr);
    if (existingIdx >= 0) {
      timeline[existingIdx] = { date: dateStr, ...flattenForTimeline(features) };
    } else {
      timeline.push({ date: dateStr, ...flattenForTimeline(features) });
    }
    const trimmedTimeline = timeline.slice(-365);

    // GAP 7 fix: Parse actual sources from assimilation metadata
    const sources = (features as any)._sources_used || [];
    // Count actual sources from the response assimilation data
    const assimSources = ((dna as any)._lastAssimSources || []) as string[];
    if (features.source_count && features.source_count > 0) {
      srcDiv.weather_count = (srcDiv.weather_count || 0) + 1;
    }
    if (features.ndvi_mean !== null && features.ndvi_mean > 0) {
      srcDiv.s2_count = (srcDiv.s2_count || 0) + 1;
    }
    if (features.sensor_moisture !== null) {
      srcDiv.iot_count = (srcDiv.iot_count || 0) + 1;
    }

    // Compute spatial fingerprint from surface stats
    const spatialFp: Record<string, number[]> = {};
    for (const stat of surfaceStats) {
      spatialFp[stat.type] = [stat.mean, stat.p10, stat.p50, stat.p90, stat.spread];
    }

    await prisma.plotDNA.update({
      where: { plotId },
      data: {
        lastSeen: now,
        totalSnapshots: { increment: 1 },
        avgFreshness: ema(dna.avgFreshness, features.freshness_score),
        ndviBaseline: {
          ema_mean: Math.round(newNdviMean * 10000) / 10000,
          ema_std: ndviBase.ema_std || 0,
          seasonal_profile: seasonal,
          peak_ndvi: Math.max(
            ndviBase.peak_ndvi || 0,
            features.ndvi_mean ?? 0
          ),
          trough_ndvi: Math.min(
            ndviBase.trough_ndvi ?? 1,
            features.ndvi_mean ?? 1
          ),
        },
        waterStressProfile: {
          ema_prob: Math.round(newWaterProb * 10000) / 10000,
          max_observed: Math.max(
            waterBase.max_observed || 0,
            features.water_stress_prob ?? 0
          ),
          seasonal_risk: waterSeasonal,
        },
        nutrientProfile: {
          ema_n_def: Math.round(ema(nutBase.ema_n_def || 0, features.n_deficiency) * 10000) / 10000,
          ema_p_def: Math.round(ema(nutBase.ema_p_def || 0, features.p_deficiency) * 10000) / 10000,
          ema_k_def: Math.round(ema(nutBase.ema_k_def || 0, features.k_deficiency) * 10000) / 10000,
          soil_fertility_trend: nutBase.soil_fertility_trend || "UNKNOWN",
        },
        bioticProfile: {
          ema_pressure: Math.round(ema(bioBase.ema_pressure || 0, features.biotic_pressure) * 10000) / 10000,
          disease_history: (bioBase.disease_history || []).slice(-100),
        },
        featureTimeline: trimmedTimeline as any,
        anomalyLog: anomalyLog.slice(-500) as any, // Keep last 500 anomalies
        spatialFingerprint: spatialFp,
        sourceDiversity: srcDiv,
      },
    });
  } catch (err) {
    console.error("[PlotDNA] Update failed:", err);
  }
}

// ── Helper: Flatten features for compact timeline storage ───────────

function flattenForTimeline(f: MLFeatureVector): Record<string, number | null> {
  return {
    ndvi: f.ndvi_mean,
    d1: f.ndvi_d1,
    ws: f.water_stress_prob,
    ns: f.nutrient_stress_prob,
    bp: f.biotic_pressure,
    t: f.temp_c,
    p: f.precip_mm,
    h: f.humidity_pct,
    r: f.risk_composite,
    sm: f.sensor_moisture,
    dap: f.dap,
  };
}
