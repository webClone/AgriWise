"use client";

import React from "react";
import { summarizeWorldModelV1View } from "@/lib/agribrain/historical-world-model-view.mjs";

export interface HistoricalIntelligencePayload {
  available: boolean;
  reason?: string | null;
  plot_id: string;
  tenant_id: string;
  geometry_hash: string;
  as_of_date: string;
  valid_time_T: string;
  knowledge_cutoff_K?: string | null;
  publication_authority: string;
  claims_numerical_authority: boolean;
  worldline_authority: string;
  qualification?: {
    passed?: boolean;
    block_reasons?: string[];
  };
  available_dates: string[];
  assimilated_observation_count: number;
  last_observation_time?: string | null;
  days_since_last_observation?: number | null;
  state_means: Record<string, number>;
  state_stds: Record<string, number>;
  state_support_ledger: Record<
    string,
    {
      state?: string;
      accepted_update_count?: number;
      support_status?: string;
      spatial_support?: string;
      block_reasons?: string[];
    }
  >;
  canonical_grid?: {
    crs?: string;
    height?: number;
    width?: number;
    bounds?: number[];
    resolution_m?: number;
  } | null;
  has_spatial_observations: boolean;
  spatial_estimation_mode?: string;
  effective_resolution_by_state?: Record<string, number | null>;
  resolution_summary_by_state?: Record<
    string,
    {
      base_m?: number;
      min_m?: number;
      median_m?: number;
      max_m?: number;
      is_spatially_varying?: boolean;
      edge_degraded_pixels?: number;
      low_support_pixels?: number;
      high_dispersion_pixels?: number;
    }
  >;
  weather_provenance_summary?: {
    total_days?: number;
    source_roles?: string[];
    reanalysis_backfill_days?: number;
    max_reanalysis_lag_days?: number;
    weather_availability_note?: string;
  };
  suppressed_spatial_states?: Record<string, { spatial_support?: string; reason?: string | null }>;
  temporal_query_scope?: {
    mode?: string;
    valid_time_T?: string;
    knowledge_cutoff_K?: string;
    has_explicit_knowledge_cutoff?: boolean;
    is_full_tail_epoch?: boolean;
    contains_post_cutoff_data?: boolean;
    ablation_scope?: string;
  };
  archive_state_version?: string;
  spatial_surfaces: any[];
  cross_layer_pre_priors?: Record<string, any>;
  cross_layer_intelligence?: {
    contract_version?: string;
    observation_role?: string;
    eligible_for_asmae_assimilation?: boolean;
    layer8_constraints_only?: boolean;
    cross_layer_agreement?: string;
    contradictions?: Array<{
      layer?: string;
      code?: string;
      severity?: string;
      description?: string;
    }>;
    trust_monitor?: Record<string, any>;
    competing_attribution?: {
      hypotheses?: Record<string, number>;
      dominant_hypothesis?: string;
      ambiguity_score?: number;
      attribution_uncertainty_note?: string;
      ranked_mechanisms?: Array<{
        mechanism: string;
        weight: number;
        evidence_basis?: string;
        verification_status?: string;
      }>;
    };
    ranked_stress_mechanisms?: Array<{
      mechanism: string;
      weight: number;
      evidence_basis?: string;
      verification_status?: string;
    }>;
    next_best_observation?: {
      observation_type?: string;
      voi_score?: number;
      reduces_uncertainty_for?: string[];
      rationale?: string;
    };
    value_of_information_ranking?: Array<{
      observation_type: string;
      voi_score: number;
      rationale: string;
    }>;
    layers_refined?: Record<string, any>;
    engines_executed?: string[];
  };
  causal_forecasts?: Array<{
    horizon_days: number;
    target_valid_time: string;
    predicted_states?: Record<string, number>;
    predicted_channels?: Record<
      string,
      {
        mean?: number;
        raw_mean?: number;
        sigma?: number;
      }
    >;
  }>;
  event_memory?: {
    events?: Array<{
      event_id: string;
      event_category: string;
      epistemic_class: string;
      hypothesis_status: string;
      start_time: string;
      severity?: number;
      competing_explanations?: Record<string, number>;
      outcome_measurement?: {
        status?: string;
        consistency_is_not_proof?: boolean;
        independent_observation_outcome?: Record<string, any>;
        model_state_inferred_outcome?: Record<string, any>;
      };
    }>;
    total_events_to_date?: number;
    meteorological_forcing_count?: number;
    confirmed_agronomic_count?: number;
    hypothesis_count?: number;
  };
  retrovalidation_summary?: {
    raw_uncalibrated_summary?: Record<string, any>;
    summary?: Record<string, any>;
    by_channel?: Record<string, Record<string, any>>;
    multi_horizon?: Record<string, any>;
    bma?: Record<string, any>;
    qualification?: Record<string, any>;
  };
  cross_layer_ablation?: {
    cross_layer_rmse?: number | null;
    s1_s2_only_rmse?: number | null;
    delta_rmse_cross_minus_s1s2?: number | null;
    skill_gain_vs_s1_s2_only?: number | null;
    cross_layer_crps?: number | null;
    s1_s2_only_crps?: number | null;
  };
  manifest_reconciliation?: {
    raw_discovered_records?: number;
    admitted_unique_count?: number;
    quarantined_duplicate_count?: number;
    reconciliation_note?: string;
  };
  world_model_contract_version?: string;
  crop_chronology_hash?: string | null;
  weather_lineage_hash?: string | null;
  cross_layer_prior_version?: string | null;
  withheld_reprocessed_after_k_count?: number;
  domain_identity?: {
    resolved_crop_code?: string;
    crop_identity_verified?: boolean;
    crop_declaration_authority?: string | null;
    tenant_identity_verified?: boolean;
    tenant_ownership_source?: string | null;
    is_isolated_dev_fixture?: boolean;
    synthetic_label_rejected?: boolean;
    crop_resolution_source?: string;
    soil_texture?: string;
    identity_block_reasons?: string[];
  } | null;
  crop_context_as_of?: {
    crop?: string | null;
    declared_crop?: string | null;
    crop_identity_verified?: boolean;
    crop_declaration_authority?: string | null;
    physical_regime?: string | null;
    unknown_probability?: number | null;
    crop_group_posterior?: Record<string, number> | null;
    crop_lineage_id?: string | null;
  } | null;
  crop_identity_timeline?: Array<{
    season_id?: string;
    start_time?: string;
    end_time?: string;
    physical_regime?: string;
    top_group?: string;
    top_group_probability?: number;
    unknown_probability?: number;
    crop_identity_verified_as_of_tk?: boolean;
    verified_crop_code_as_of_tk?: string | null;
    species_probability_published?: boolean;
  }>;
  exploratory_by_horizon?: Record<string, Record<string, any>>;
  scientific_failure_diagnosis?: {
    primary_cause?: string | null;
    causes?: string[];
    recommended_evidence_to_unblock?: string[];
  } | null;
  causal_integrity_gates?: Record<string, boolean>;
}

const PRESET_DATES = [
  { id: "2018", date: "2018-07-15", label: "2018-07" },
  { id: "2021", date: "2021-04-15", label: "2021-04" },
  { id: "2026", date: "2026-09-01", label: "2026-09" },
] as const;

const EPISTEMIC_BADGES: Record<string, { label: string; color: string; bg: string }> = {
  meteorological_forcing_reanalysis: {
    label: "METEOROLOGICAL FORCING",
    color: "#38bdf8",
    bg: "rgba(56, 189, 248, 0.14)",
  },
  agronomic_event_confirmed: {
    label: "CONFIRMED AGRONOMIC",
    color: "#34d399",
    bg: "rgba(52, 211, 153, 0.14)",
  },
  model_hypothesis: {
    label: "MODEL HYPOTHESIS",
    color: "#f59e0b",
    bg: "rgba(245, 158, 11, 0.14)",
  },
};

export default function HistoricalIntelligencePanel({
  activeAsOfDate,
  loading,
  error,
  data,
  onSelectDate,
  onReturnToLive,
}: {
  activeAsOfDate: string | null;
  loading: boolean;
  error: string | null;
  data: HistoricalIntelligencePayload | null;
  onSelectDate: (dateIso: string) => void;
  onReturnToLive: () => void;
}) {
  const cl = data?.cross_layer_intelligence;
  const refined = cl?.layers_refined || {};
  const voi = cl?.next_best_observation;
  const contradictions = cl?.contradictions || [];
  const hypotheses = cl?.competing_attribution?.hypotheses || {};
  const retroSum = data?.retrovalidation_summary?.summary || {};
  const rawRetroSum = data?.retrovalidation_summary?.raw_uncalibrated_summary || {};
  const multiHorizon = data?.retrovalidation_summary?.multi_horizon?.by_horizon || {};
  const wmView = summarizeWorldModelV1View(data);
  const domId = data?.domain_identity;
  const cropAsOf = data?.crop_context_as_of;
  const ablation = data?.cross_layer_ablation || {};
  const mem = data?.event_memory;
  const recentEvents = [...(mem?.events || [])].reverse().slice(0, 6);
  const availDates = data?.available_dates || [];
  const isHistoricalActive = Boolean(activeAsOfDate);

  return (
    <div
      data-testid="hist-world-model-panel"
      style={{
        marginTop: "14px",
        padding: "12px",
        borderRadius: "10px",
        background: isHistoricalActive
          ? "linear-gradient(145deg, rgba(14, 116, 144, 0.18), rgba(15, 23, 42, 0.72))"
          : "rgba(15, 23, 42, 0.52)",
        border: isHistoricalActive
          ? "1px solid rgba(56, 189, 248, 0.45)"
          : "1px solid rgba(148, 163, 184, 0.18)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
        <div>
          <div style={{ fontSize: "11px", fontWeight: 800, letterSpacing: "0.05em", color: "#38bdf8", textTransform: "uppercase" }}>
            Historical World Model · L2–8
          </div>
          <div style={{ fontSize: "10px", color: "#94a3b8" }}>
            {isHistoricalActive
              ? `Time-travel active as of ${activeAsOfDate} (diagnostic spatial rebuild)`
              : "Explore 2015–present causal states & cross-layer coupling"}
          </div>
        </div>
        {isHistoricalActive && (
          <button
            type="button"
            data-testid="hist-return-live"
            onClick={onReturnToLive}
            style={{
              padding: "4px 8px",
              fontSize: "10px",
              fontWeight: 700,
              borderRadius: "6px",
              border: "1px solid rgba(248, 113, 113, 0.45)",
              background: "rgba(248, 113, 113, 0.14)",
              color: "#fca5a5",
              cursor: "pointer",
            }}
          >
            Return to Live
          </button>
        )}
      </div>

      {/* Preset Epochs & Causal Date Selector */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px" }}>
        {PRESET_DATES.map((preset) => {
          const isSelected = activeAsOfDate === preset.date;
          return (
            <button
              key={preset.id}
              type="button"
              data-testid={`hist-preset-${preset.id}`}
              onClick={() => onSelectDate(preset.date)}
              style={{
                padding: "4px 8px",
                fontSize: "10px",
                fontWeight: 700,
                borderRadius: "6px",
                border: isSelected ? "1px solid #38bdf8" : "1px solid rgba(148, 163, 184, 0.25)",
                background: isSelected ? "rgba(56, 189, 248, 0.22)" : "rgba(15, 23, 42, 0.65)",
                color: isSelected ? "#e0f2fe" : "#cbd5e1",
                cursor: "pointer",
              }}
            >
              {preset.label}
            </button>
          );
        })}
        <input
          type="date"
          aria-label="Historical valid date"
          data-testid="hist-date-input"
          value={activeAsOfDate || ""}
          min={availDates[0] || "2015-06-23"}
          max="2026-12-31"
          onChange={(e) => {
            if (e.target.value) onSelectDate(e.target.value);
          }}
          style={{
            background: "rgba(15, 23, 42, 0.85)",
            color: "#e2e8f0",
            border: "1px solid rgba(148, 163, 184, 0.3)",
            borderRadius: "6px",
            fontSize: "10px",
            padding: "3px 6px",
          }}
        />
      </div>

      {availDates.length > 0 && (
        <div style={{ marginBottom: "8px" }}>
          <select
            aria-label="Jump to historical scene acquisition date"
            data-testid="hist-scene-select"
            value={activeAsOfDate && availDates.includes(activeAsOfDate) ? activeAsOfDate : ""}
            onChange={(e) => {
              if (e.target.value) onSelectDate(e.target.value);
            }}
            style={{
              width: "100%",
              background: "rgba(15, 23, 42, 0.8)",
              color: "#cbd5e1",
              border: "1px solid rgba(148, 163, 184, 0.25)",
              borderRadius: "6px",
              fontSize: "10px",
              padding: "4px 6px",
            }}
          >
            <option value="">Jump to qualified S1/S2 scene ({availDates.length} dates)...</option>
            {availDates
              .slice()
              .reverse()
              .map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
          </select>
        </div>
      )}

      {loading && (
        <div data-testid="hist-loading" style={{ fontSize: "11px", color: "#7dd3fc", padding: "6px 0" }}>
          Reconstructing causal L2–8 state as of {activeAsOfDate}...
        </div>
      )}

      {error && (
        <div data-testid="hist-error" style={{ fontSize: "11px", color: "#fca5a5", padding: "6px 0" }}>
          Historical state unavailable: {error}
        </div>
      )}

      {!loading && data && !data.available && (
        <div style={{ fontSize: "11px", color: "#fbbf24", padding: "4px 0" }}>
          No qualified satellite observations on or before {activeAsOfDate}.
        </div>
      )}

      {!loading && data && data.available && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {/* Epistemic Authority & Assimilation Summary */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "6px",
              padding: "8px",
              borderRadius: "8px",
              background: "rgba(2, 6, 23, 0.45)",
              border: "1px solid rgba(148, 163, 184, 0.14)",
              fontSize: "10px",
            }}
          >
            <div>
              <div style={{ color: "#94a3b8" }}>Worldline Authority</div>
              <div style={{ color: data.worldline_authority === "ARCHIVE_POSTERIOR_VALIDATED" ? "#34d399" : "#fbbf24", fontWeight: 700, fontFamily: "monospace" }}>
                {data.worldline_authority}
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8" }}>Assimilated Scenes (≤ T)</div>
              <div style={{ color: "#e2e8f0", fontWeight: 700 }}>
                {data.assimilated_observation_count} obs · {data.spatial_surfaces?.length || 0} spatial maps
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8" }}>Canonical Grid</div>
              <div style={{ color: "#cbd5e1", fontFamily: "monospace" }}>
                {data.canonical_grid ? `${data.canonical_grid.height}×${data.canonical_grid.width} (${data.canonical_grid.resolution_m ?? 10}m base)` : "Scalar"}
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8" }}>State Age</div>
              <div style={{ color: "#cbd5e1" }}>
                {data.days_since_last_observation ?? 0}d since last obs
              </div>
            </div>
            {data.effective_resolution_by_state && Object.keys(data.effective_resolution_by_state).length > 0 && (
              <div style={{ gridColumn: "1 / -1", borderTop: "1px solid rgba(148,163,184,0.12)", paddingTop: "5px" }}>
                <div style={{ color: "#94a3b8" }}>Adaptive Spatial Support (1m Held)</div>
                <div style={{ color: "#7dd3fc", fontFamily: "monospace", fontSize: "9.5px" }}>
                  {[...new Set(Object.values(data.effective_resolution_by_state).filter((v): v is number => typeof v === "number"))]
                    .sort((a, b) => a - b)
                    .map((r) => `${r}m`)
                    .join(" / ")}{" "}
                  across {Object.keys(data.effective_resolution_by_state).length} states
                  {Object.values(data.resolution_summary_by_state || {}).some((rs) => rs?.is_spatially_varying)
                    ? ` · locally varying (${Math.min(
                        ...Object.values(data.resolution_summary_by_state || {})
                          .map((rs) => rs?.min_m ?? 999)
                      )}–${Math.max(
                        ...Object.values(data.resolution_summary_by_state || {})
                          .map((rs) => rs?.max_m ?? 0)
                      )}m)`
                    : ""}
                  {data.suppressed_spatial_states && Object.keys(data.suppressed_spatial_states).length > 0
                    ? ` · ${Object.keys(data.suppressed_spatial_states).length} scalar/withheld`
                    : ""}
                </div>
              </div>
            )}
          </div>

          {/* Cross-Layer Specialist Intelligence (L2–L8, non-assimilable) */}
          {cl && (
            <div
              data-testid="hist-cross-layer"
              style={{
                padding: "8px",
                borderRadius: "8px",
                background: "rgba(2, 6, 23, 0.45)",
                border: "1px solid rgba(148, 163, 184, 0.14)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "10px", fontWeight: 750, color: "#a7f3d0", textTransform: "uppercase" }}>
                  L2–8 Cross-Layer Intelligence ({cl.engines_executed?.length || 0} engines)
                </span>
                <span
                  style={{
                    fontSize: "9px",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    fontWeight: 700,
                    background: contradictions.length > 0 ? "rgba(245, 158, 11, 0.2)" : "rgba(52, 211, 153, 0.16)",
                    color: contradictions.length > 0 ? "#fcd34d" : "#6ee7b7",
                  }}
                >
                  {cl.cross_layer_agreement || "consistent"}
                </span>
              </div>
              <div style={{ fontSize: "9.5px", color: "#94a3b8", marginBottom: "6px" }}>
                Role: <code style={{ color: "#cbd5e1" }}>{cl.observation_role}</code> · Layer 8:{" "}
                <span style={{ color: "#cbd5e1" }}>constraints-only (no recommendations)</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 8px", fontSize: "10px" }}>
                <div>
                  <span style={{ color: "#94a3b8" }}>L2 Phenology: </span>
                  <strong style={{ color: "#e2e8f0" }}>{refined.layer2_vegetation?.phenology_stage ?? "N/A"}</strong>
                </div>
                <div>
                  <span style={{ color: "#94a3b8" }}>L3 ET0 / Water Lim: </span>
                  <strong style={{ color: "#38bdf8" }}>
                    {refined.layer3_water?.et0 ?? "—"}mm · {Math.round((refined.layer3_water?.refined_water_stress_prob ?? 0) * 100)}%
                  </strong>
                </div>
                <div>
                  <span style={{ color: "#94a3b8" }}>L4 N-Def / NNI: </span>
                  <strong style={{ color: "#e2e8f0" }}>
                    {Math.round((refined.layer4_nutrients?.refined_n_deficiency_prob ?? 0) * 100)}% · NNI {refined.layer4_nutrients?.nitrogen_nutrition_index ?? "—"}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "#94a3b8" }}>L5 Path. Confounder: </span>
                  <strong style={{ color: "#fbbf24" }}>{refined.layer5_biotic?.top_threat_hypothesis ?? "none"}</strong>
                </div>
                <div>
                  <span style={{ color: "#94a3b8" }}>L6 Yield Est.: </span>
                  <strong style={{ color: "#e2e8f0" }}>{refined.layer6_yield?.predicted_yield_t_ha ?? "—"} t/ha</strong>
                </div>
                <div>
                  <span style={{ color: "#94a3b8" }}>L7 Risk Level: </span>
                  <strong style={{ color: "#e2e8f0" }}>{refined.layer7_risk?.risk_level ?? "low"}</strong>
                </div>
              </div>

              {contradictions.length > 0 && (
                <div style={{ marginTop: "6px", paddingTop: "6px", borderTop: "1px dashed rgba(245,158,11,0.25)" }}>
                  <div style={{ fontSize: "9.5px", fontWeight: 700, color: "#fbbf24" }}>Cross-Layer Contradictions</div>
                  {contradictions.slice(0, 3).map((c, idx) => (
                    <div key={`${c.code || idx}`} style={{ fontSize: "9.5px", color: "#fde68a", marginTop: "2px" }}>
                      • [{c.layer}] {c.description}
                    </div>
                  ))}
                </div>
              )}

              {((cl?.ranked_stress_mechanisms && cl.ranked_stress_mechanisms.length > 0) ||
                Object.keys(hypotheses).length > 0) && (
                <div style={{ marginTop: "6px", fontSize: "9.5px", color: "#cbd5e1" }}>
                  <span style={{ color: "#94a3b8" }}>Ranked Mechanisms (Hypothesis vs Verified): </span>
                  {cl?.ranked_stress_mechanisms && cl.ranked_stress_mechanisms.length > 0
                    ? cl.ranked_stress_mechanisms
                        .slice(0, 4)
                        .map(
                          (m) =>
                            `${m.mechanism.replaceAll("_", " ")} (${Math.round(m.weight * 100)}%, ${
                              m.verification_status === "measured_soil_ec" ? "measured" : "hypothesis"
                            })`
                        )
                        .join(" · ")
                    : Object.entries(hypotheses)
                        .filter(([, v]) => typeof v === "number")
                        .map(([k, v]) => `${k.replaceAll("_", " ")} (${Math.round(Number(v) * 100)}%)`)
                        .join(" · ")}
                </div>
              )}
            </div>
          )}

          {/* Value of Information Next-Best Observation */}
          {voi && (
            <div
              data-testid="hist-voi-card"
              style={{
                padding: "8px",
                borderRadius: "8px",
                background: "rgba(56, 189, 248, 0.08)",
                border: "1px solid rgba(56, 189, 248, 0.25)",
                fontSize: "10px",
              }}
            >
              <div style={{ fontWeight: 750, color: "#7dd3fc", textTransform: "uppercase", fontSize: "9.5px" }}>
                Next-Best Observation (VoI Rank #1 · Score {voi.voi_score})
              </div>
              <div style={{ color: "#f1f5f9", fontWeight: 700, marginTop: "2px" }}>
                {(voi.observation_type || "").replaceAll("_", " ")}
              </div>
              <div style={{ color: "#94a3b8", fontSize: "9.5px", marginTop: "2px" }}>{voi.rationale}</div>
            </div>
          )}

          {/* Causal Forward Forecasts (issued strictly from <= T) */}
          {data.causal_forecasts && data.causal_forecasts.length > 0 && (
            <div
              data-testid="hist-causal-forecasts"
              style={{
                padding: "8px",
                borderRadius: "8px",
                background: "rgba(2, 6, 23, 0.45)",
                border: "1px solid rgba(148, 163, 184, 0.14)",
                fontSize: "10px",
              }}
            >
              <div style={{ fontWeight: 750, color: "#cbd5e1", textTransform: "uppercase", fontSize: "9.5px", marginBottom: "4px" }}>
                Causal Multi-Horizon Forecasts (Issued @ {data.as_of_date})
              </div>
              {data.causal_forecasts.map((fc) => (
                <div
                  key={fc.horizon_days}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "9.5px",
                    padding: "2px 0",
                    borderBottom: "1px solid rgba(148,163,184,0.08)",
                  }}
                >
                  <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>+{fc.horizon_days}d</span>
                  <span style={{ color: "#e2e8f0" }}>
                    NDVI {fc.predicted_channels?.ndvi?.mean?.toFixed(3) ?? "—"} ± {fc.predicted_channels?.ndvi?.sigma?.toFixed(3) ?? "—"}
                  </span>
                  <span style={{ color: "#38bdf8" }}>
                    NDMI {fc.predicted_channels?.ndmi?.mean?.toFixed(3) ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Retrovalidation & L2-8 Ablation Metrics */}
          {retroSum.rmse !== undefined && (
            <div
              style={{
                padding: "8px",
                borderRadius: "8px",
                background: "rgba(2, 6, 23, 0.45)",
                border: "1px solid rgba(148, 163, 184, 0.14)",
                fontSize: "9.5px",
                color: "#cbd5e1",
              }}
            >
              <div style={{ fontWeight: 750, color: "#cbd5e1", textTransform: "uppercase", marginBottom: "4px" }}>
                Empirical Skill (≤ {data.as_of_date}, n={retroSum.n_evaluated_points ?? 0})
              </div>
              <div>
                RMSE: {rawRetroSum.rmse} (raw) → <strong style={{ color: "#34d399" }}>{retroSum.rmse}</strong> (cal) · Cov{" "}
                {Math.round((retroSum.coverage_1sigma || 0) * 100)}% / {Math.round((retroSum.coverage_2sigma || 0) * 100)}%
              </div>
              <div>
                Skill vs Clim: <strong style={{ color: "#34d399" }}>{retroSum.skill_vs_climatology}</strong> · Prospective 17–35d:{" "}
                <strong style={{ color: "#38bdf8" }}>{multiHorizon.extended_17_35d?.skill_vs_persistence ?? "Sub-slice N/A"}</strong>
              </div>
              <div style={{ color: "#94a3b8", fontSize: "9px" }}>
                Spatial maps: inferred state anomaly fields ({data.spatial_estimation_mode || "model + S1/S2 anomalies"}, not direct physical pixel sensors).
                {data.weather_provenance_summary?.reanalysis_backfill_days
                  ? ` Weather: ERA5 reanalysis (${data.weather_provenance_summary.max_reanalysis_lag_days ?? 5}d lag metadata).`
                  : ""}
              </div>
              {ablation.s1_s2_only_rmse != null && (
                <div>
                  Combined L2–8 vs S1/S2-only: <strong>{ablation.cross_layer_rmse}</strong> vs {ablation.s1_s2_only_rmse} (Δ{" "}
                  {ablation.delta_rmse_cross_minus_s1s2})
                </div>
              )}
              {wmView.exploratory36_90d && (
                <div style={{ color: "#94a3b8", fontSize: "9.5px", marginTop: "2px" }}>
                  Exploratory 36–90d (not qualification gate): skill{" "}
                  <strong style={{ color: "#cbd5e1" }}>
                    {wmView.exploratory36_90d.skillVsPersistence ?? "N/A"}
                  </strong>{" "}
                  (RMSE {wmView.exploratory36_90d.rmse ?? "N/A"})
                </div>
              )}
            </div>
          )}

          {/* World Model V1: Domain Verification, Historical P(C_t | O<=t, K), and Scientific Failure Diagnosis */}
          {(domId || cropAsOf || wmView.latestEoGroup || wmView.primaryFailureCause) && (
            <div
              data-testid="hist-world-model-diagnostics"
              style={{
                padding: "8px",
                borderRadius: "8px",
                background: "rgba(2, 6, 23, 0.48)",
                border: "1px solid rgba(56, 189, 248, 0.22)",
                fontSize: "10px",
                color: "#cbd5e1",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "4px" }}>
                <span style={{ fontWeight: 700, color: "#7dd3fc" }}>Crop Identity & Domain Authority (V2)</span>
                {wmView.cropBadgeLabel && (
                  <span
                    data-testid="hist-domain-identity-badge"
                    style={{
                      fontSize: "9px",
                      fontWeight: 700,
                      padding: "1px 6px",
                      borderRadius: "999px",
                      background: wmView.cropVerified
                        ? "rgba(16, 185, 129, 0.16)"
                        : "rgba(245, 158, 11, 0.18)",
                      color: wmView.cropVerified ? "#34d399" : "#fbbf24",
                    }}
                  >
                    {wmView.cropBadgeLabel}
                  </span>
                )}
              </div>
              {domId && (
                <div style={{ fontSize: "9.5px", color: "#94a3b8" }}>
                  Tenant: {wmView.tenantLabel}
                  {wmView.tenantOwnershipSource ? ` (${wmView.tenantOwnershipSource})` : ""}
                  {wmView.cropDeclarationAuthority ? ` · Authority: ${wmView.cropDeclarationAuthority}` : ""}
                  {wmView.syntheticRejected ? " · Synthetic training seed rejected" : ""}
                  {domId.soil_texture ? ` · Soil: ${domId.soil_texture}` : ""}
                </div>
              )}
              {cropAsOf && (
                <div style={{ fontSize: "9.5px" }}>
                  As-of P(C_t | O≤t, K):{" "}
                  <strong>{wmView.asOfCropLabel}</strong> · Regime:{" "}
                  <span style={{ color: "#e2e8f0" }}>{wmView.physicalRegime || "UNVERIFIED"}</span>
                  {wmView.unknownMassPct !== null ? ` · Unknown mass: ${wmView.unknownMassPct}%` : ""}
                </div>
              )}
              {wmView.preKnownCycleUnknown && (
                <div style={{ fontSize: "9px", color: "#fcd34d" }}>
                  Pre-cycle unknown period (no unverified fallow/soil-prep assumption claimed)
                </div>
              )}
              {wmView.withheldReprocessedAfterK > 0 && (
                <div style={{ fontSize: "9px", color: "#93c5fd" }}>
                  Withheld reprocessed/future-K products (&gt;K): {wmView.withheldReprocessedAfterK}
                </div>
              )}
              {wmView.latestEoGroup && (
                <div style={{ fontSize: "9px", color: "#94a3b8" }}>
                  Latest Season EO Group:{" "}
                  <span style={{ color: "#cbd5e1" }}>
                    {wmView.latestEoGroup} (uncalibrated group ranking)
                  </span>
                </div>
              )}
              {(wmView.cropChronologyHash || wmView.weatherLineageHash) && (
                <div style={{ fontSize: "8.5px", color: "#64748b", fontFamily: "monospace" }}>
                  Lineage: crop={wmView.cropChronologyHash ? wmView.cropChronologyHash.slice(0, 10) : "n/a"} · weather={wmView.weatherLineageHash ? wmView.weatherLineageHash.slice(0, 10) : "n/a"}
                  {wmView.crossLayerPriorVersion ? ` · prior=${wmView.crossLayerPriorVersion}` : ""}
                </div>
              )}
              {wmView.primaryFailureCause && (
                <div style={{ fontSize: "9.5px", color: "#fda4af" }}>
                  Scientific Blocker: <strong>{wmView.primaryFailureCause}</strong>
                  {wmView.primaryFailureAction ? ` — ${wmView.primaryFailureAction}` : ""}
                </div>
              )}
            </div>
          )}

          {/* 4-Tier Causal Event Memory (<= T) */}
          {recentEvents.length > 0 && (
            <div
              data-testid="hist-event-memory"
              style={{
                padding: "8px",
                borderRadius: "8px",
                background: "rgba(2, 6, 23, 0.45)",
                border: "1px solid rgba(148, 163, 184, 0.14)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9.5px", color: "#cbd5e1", marginBottom: "4px" }}>
                <span style={{ fontWeight: 750, textTransform: "uppercase" }}>4-Tier Event Memory (≤ {data.as_of_date})</span>
                <span style={{ color: "#94a3b8" }}>{mem?.total_events_to_date ?? recentEvents.length} total</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "180px", overflowY: "auto" }}>
                {recentEvents.map((ev) => {
                  const badge = EPISTEMIC_BADGES[ev.epistemic_class] || {
                    label: ev.epistemic_class,
                    color: "#cbd5e1",
                    bg: "rgba(148, 163, 184, 0.14)",
                  };
                  return (
                    <div
                      key={ev.event_id}
                      style={{
                        padding: "5px 6px",
                        borderRadius: "6px",
                        background: "rgba(15, 23, 42, 0.7)",
                        border: "1px solid rgba(148, 163, 184, 0.12)",
                        fontSize: "9.5px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "4px", alignItems: "center" }}>
                        <span style={{ color: badge.color, background: badge.bg, padding: "1px 4px", borderRadius: "3px", fontSize: "8.5px", fontWeight: 700 }}>
                          {badge.label}
                        </span>
                        <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{ev.start_time.slice(0, 10)}</span>
                      </div>
                      <div style={{ color: "#e2e8f0", marginTop: "2px", fontWeight: 600 }}>
                        {ev.event_category.replaceAll("_", " ")} · <span style={{ color: "#94a3b8" }}>{ev.hypothesis_status}</span>
                      </div>
                      {ev.outcome_measurement?.independent_observation_outcome?.delta_obs_ndvi != null && (
                        <div style={{ color: "#7dd3fc", fontSize: "9px" }}>
                          Subsequent Obs Outcome: ΔNDVI {ev.outcome_measurement.independent_observation_outcome.delta_obs_ndvi}
                          {ev.outcome_measurement.consistency_is_not_proof ? " (consistency ≠ proof)" : ""}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
