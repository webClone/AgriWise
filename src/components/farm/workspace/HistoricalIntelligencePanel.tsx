"use client";

import React from "react";

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
    };
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
                {data.canonical_grid ? `${data.canonical_grid.height}×${data.canonical_grid.width} (${data.canonical_grid.resolution_m ?? 10}m)` : "Scalar"}
              </div>
            </div>
            <div>
              <div style={{ color: "#94a3b8" }}>State Age</div>
              <div style={{ color: "#cbd5e1" }}>
                {data.days_since_last_observation ?? 0}d since last obs
              </div>
            </div>
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

              {Object.keys(hypotheses).length > 0 && (
                <div style={{ marginTop: "6px", fontSize: "9.5px", color: "#cbd5e1" }}>
                  <span style={{ color: "#94a3b8" }}>Competing Hypotheses: </span>
                  {Object.entries(hypotheses)
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
                Empirical Skill & L2–8 Ablation
              </div>
              <div>
                RMSE: {rawRetroSum.rmse} (raw) → <strong style={{ color: "#34d399" }}>{retroSum.rmse}</strong> (cal) · Cov{" "}
                {Math.round((retroSum.coverage_1sigma || 0) * 100)}% / {Math.round((retroSum.coverage_2sigma || 0) * 100)}%
              </div>
              <div>
                Skill vs Clim: <strong style={{ color: "#34d399" }}>{retroSum.skill_vs_climatology}</strong> · 17–35d Skill vs Pers:{" "}
                <strong style={{ color: "#38bdf8" }}>{multiHorizon.extended_17_35d?.skill_vs_persistence ?? "—"}</strong>
              </div>
              {ablation.s1_s2_only_rmse != null && (
                <div>
                  Combined L2–8 vs S1/S2-only: <strong>{ablation.cross_layer_rmse}</strong> vs {ablation.s1_s2_only_rmse} (Δ{" "}
                  {ablation.delta_rmse_cross_minus_s1s2})
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
