"""
Layer 10 Frontend Bridge
========================
Standalone script called from Node.js to run the L10 pipeline
and return structured JSON for the frontend.

Usage:
  py l10_frontend_bridge.py --context <base64_json>

The context JSON should contain:
  { plotId, lat, lng, crop, sensors, zones, ... }
"""
import sys
import os
import json
import base64
import argparse
import random

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceType, GroundingClass,
    ExplainabilityPack, DriverWeight, ModelEquation, 
    ExplainabilityProvenance, ExplainabilityConfidence, ConfidencePenalty
)
from services.agribrain.layer10_sire.runner import run_layer10_sire
from layer1_fusion.schema import FieldTensor, FieldTensorChannels
from layer1_fusion.raster_backend import GridSpec
from layer2_veg_int.schema import (
    VegIntOutput, ModeledCurveOutput, CurveQuality, PhenologyOutput, SpatialMetrics,
)
from types import SimpleNamespace
from services.agribrain.layer10_sire.surface_contract import (
    build_default_asmae_proof,
    build_no_data_render_authorizations,
)
from services.agribrain.scientific_contracts.crop_phenology import (
    normalize_published_phenology,
)


def build_input_from_context(ctx: dict) -> Layer10Input:
    """Build a Layer10Input from frontend context."""
    plot_id = ctx.get('plotId', 'UNKNOWN')
    lat = ctx.get('lat', 36.0)
    lng = ctx.get('lng', 3.0)
    crop = ctx.get('crop', 'wheat')

    H, W = 8, 8
    T, C = 15, 5  # 15 time steps for full 14-day window testing
    random.seed(hash(plot_id) % 2**31)

    # Build synthetic field tensor from plot location
    data_4d = [[[[0.0]*C for _ in range(W)] for _ in range(H)] for _ in range(T)]
    for t in range(T):
        for r in range(H):
            for c in range(W):
                dist = ((r - 3.5)**2 + (c - 3.5)**2)**0.5 / 5.0
                ndvi = max(0.1, min(0.95, 0.4 + t * 0.02 - dist * 0.2 + random.uniform(-0.04, 0.04)))
                unc = 0.03 + random.uniform(0, 0.04)
                vv = -12.0 + random.uniform(-2, 2)
                vh = -18.0 + random.uniform(-2, 2)
                precip = max(0, 3.0 + random.uniform(-1, 3))
                data_4d[t][r][c] = [ndvi, unc, vv, vh, precip]

    ft = FieldTensor(
        plot_id=plot_id, run_id=f'L1-{plot_id[:8]}',
        grid_spec=GridSpec(
            crs='EPSG:4326',
            transform=(lng, 0.00009, 0, lat, 0, -0.00009),
            width=W, height=H,
            bounds=(lng, lat - H * 0.00009, lng + W * 0.00009, lat),
            resolution=10.0
        ),
        time_index=[f'2025-06-{16 + i:02d}' for i in range(T)],  # 15-day window
        channels=[
            FieldTensorChannels.NDVI, FieldTensorChannels.NDVI_UNC,
            FieldTensorChannels.VV, FieldTensorChannels.VH,
            FieldTensorChannels.PRECIPITATION,
        ],
        data=data_4d,
        zones={
            'zone_a': {'mask': [[r < 4 for c in range(W)] for r in range(H)], 'area_pct': 50, 'label': 'North'},
            'zone_b': {'mask': [[r >= 4 for c in range(W)] for r in range(H)], 'area_pct': 50, 'label': 'South'},
        },
        daily_state={'ndvi': [0.5 + 0.01 * d for d in range(T)], 'precipitation': [5.0]*10 + [0.0]*5},
        provenance_log=[{'day': f'2025-06-{16 + T - 1}', 'sources': {'s2': 0.5, 's1': 0.2, 'weather': 0.2, 'soil': 0.1}}],
    )

    vi = VegIntOutput(
        run_id=f'L2-{plot_id[:8]}', layer1_run_id=f'L1-{plot_id[:8]}',
        curve=ModeledCurveOutput(
            ndvi_fit=[0.5]*30, ndvi_fit_d1=[0.01]*30,
            quality=CurveQuality(rmse=0.02, outlier_frac=0.01, obs_coverage=0.85),
            ndvi_fit_unc=[0.05]*30
        ),
        # Synthetic bridge inputs carry no authoritative Layer-2 phenology receipt.
        # Do not manufacture a stage from a demo stage_by_day sequence.
        phenology=PhenologyOutput(stage_by_day=[], key_dates={}),
        anomalies=[],
        stability=SpatialMetrics(
            mean_spatial_var=0.12, std_spatial_var=0.05,
            stability_class='HETEROGENEOUS', confidence=0.8
        ),
        zone_metrics={'zone_a': {'stability_score': 0.9}, 'zone_b': {'stability_score': 0.3}},
    )

    l3 = SimpleNamespace(
        run_id_l3=f'L3-{plot_id[:8]}',
        diagnoses=[SimpleNamespace(
            problem_id='WATER_STRESS', probability=0.7, severity=0.6, confidence=0.8,
            affected_area_pct=40.0, hotspot_zone_ids=['zone_b'], drivers_used=[],
        )],
        recommendations=[], execution_plan=SimpleNamespace(tasks=[]),
        quality_metrics=SimpleNamespace(
            degradation_mode=SimpleNamespace(value='NORMAL'), decision_reliability=0.85
        ),
    )
    l4 = SimpleNamespace(
        nutrient_states={'N': SimpleNamespace(probability_deficient=0.6, confidence=0.7, severity='MODERATE')},
        run_meta=SimpleNamespace(run_id=f'L4-{plot_id[:8]}'), zone_metrics={},
    )
    l5 = SimpleNamespace(
        threat_states={'FUNGAL': SimpleNamespace(probability=0.3, spread_pattern=SimpleNamespace(value='PATCHY'))},
        weather_pressure=SimpleNamespace(composite_score=0.4),
        run_meta=SimpleNamespace(run_id=f'L5-{plot_id[:8]}'),
    )
    l7 = SimpleNamespace(
        options=[SimpleNamespace(
            suitability_percentage=75.0, crop=crop,
            yield_dist=SimpleNamespace(p10=6.0, p50=8.5, p90=10.2),
            econ=SimpleNamespace(profit_p50=1500.0),
        )],
        run_meta={'run_id': f'L7-{plot_id[:8]}'},
    )
    l8 = SimpleNamespace(
        actions=[SimpleNamespace(
            action_type=SimpleNamespace(value='IRRIGATE'), action_id='A1',
            priority_score=0.8, is_allowed=True, zone_targets=['zone_b'],
            confidence=SimpleNamespace(value='HIGH'),
        )],
        zone_plan=[], run_id=f'L8-{plot_id[:8]}', outcome_forecast=None,
        quality=SimpleNamespace(audit_grade='B', upstream_confidence={'s2': 0.8}),
        schedule=[],
    )

    # Inject ForecastContext for temporal engine testing
    from services.agribrain.layer10_sire.schema import ForecastContext
    fc = ForecastContext(
        precipitation_forecast=[3.0, 5.0, 0.0, 0.0, 2.0, 8.0, 1.0],
        temperature_max_forecast=[32.0, 33.0, 35.0, 34.0, 31.0, 29.0, 30.0],
        temperature_min_forecast=[18.0, 19.0, 21.0, 20.0, 18.0, 17.0, 18.0],
        humidity_forecast=[45.0, 50.0, 35.0, 40.0, 55.0, 60.0, 50.0],
        forecast_source='SYNTHETIC',
        forecast_confidence=0.75,
    )

    t_id = ctx.get("tenant_id") or "tenant_demo"
    f_id = ctx.get("farm_id") or "farm_demo"
    p_id = plot_id or ctx.get("plot_id") or "plot_demo"
    from services.agribrain.common.plot_namespace import PlotNamespace
    ns = ctx.get("plot_namespace") or PlotNamespace(tenant_id=t_id, farm_id=f_id, plot_id=p_id)

    return Layer10Input(
        plot_namespace=ns,
        tenant_id=ns.tenant_id,
        farm_id=ns.farm_id,
        plot_id=ns.plot_id,
        field_tensor=ft, veg_int=vi,
        decision=l3, nutrients=l4, bio=l5, planning=l7, prescriptive=l8,
        grid_height=H, grid_width=W, resolution_m=10.0,
        forecast_context=fc,
        reference_date=f'2025-06-{16 + T - 1:02d}',
        crop=crop,
        # V61: Thread ground truth context for resolution surface generator
        ground_truth_context=ctx.get('ground_truth_context', {}),
        visual_config=ctx.get('visual_config'),
        raster_composites=ctx.get('raster_composites'),
        field_geometry=geom_canon.get("canonical_geojson") or geom_context,
        canonical_geometry_hash=geom_canon.get("canonical_geometry_hash"),
        source_geometry_hash=geom_canon.get("source_geometry_hash"),
    )


def serialize_output(out) -> dict:
    """Serialize Layer10Output to a JSON-safe dict for the frontend."""
    from services.agribrain.layer10_sire.surface_contract import serialize_surface_artifact

    surfaces = [serialize_surface_artifact(surface) for surface in out.surface_pack]

    # Quality report
    qr = out.quality_report
    comp_failures = [
        f.to_dict() if hasattr(f, "to_dict")
        else dict(f) if isinstance(f, dict)
        else {
            "code": getattr(f, "code", "COMPONENT_FAILURE"),
            "component": getattr(f, "component", "unknown"),
            "stage": getattr(f, "stage", "unknown"),
            "message": getattr(f, "message", str(f)),
            "fallback_used": bool(getattr(f, "fallback_used", False)),
            "affected_surface_types": list(
                getattr(f, "affected_surface_types", []) or []
            ),
        }
        for f in getattr(qr, "component_failures", []) or []
    ]
    quality = {
        'degradation_mode': qr.degradation_mode.value,
        'reliability_score': qr.reliability_score,
        'surfaces_generated': qr.surfaces_generated,
        'surfaces_skipped': qr.surfaces_skipped,
        'zones_generated': qr.zones_generated,
        'micro_objects_detected': qr.micro_objects_detected,
        'grid_alignment_ok': qr.grid_alignment_ok,
        'detail_conservation_ok': qr.detail_conservation_ok,
        'warnings': qr.warnings,
        'missing_upstream': qr.missing_upstream,
        'component_failures': comp_failures,
        'degradation_codes': getattr(qr, 'degradation_codes', []) or [],
    }

    # Explainability Pack
    explainability_pack = {}
    for key, pack in out.explainability_pack.items():
        explainability_pack[key] = {
            'summary': pack.summary,
            'top_drivers': [
                {'name': d.name, 'value': d.value, 'role': d.role, 'description': d.description, 'formatted_value': d.formatted_value}
                for d in pack.top_drivers
            ],
            'equations': [
                {'label': eq.label, 'expression': eq.expression, 'plain_language': eq.plain_language}
                for eq in pack.equations
            ],
            'charts': pack.charts,
            'provenance': {
                'sources': pack.provenance.sources,
                'timestamps': pack.provenance.timestamps,
                'model_version': pack.provenance.model_version,
                'run_id': pack.provenance.run_id,
                'degraded_reasons': pack.provenance.degraded_reasons,
            },
            'confidence': {
                'score': pack.confidence.score,
                'penalties': [
                    {'reason': p.reason, 'impact': p.impact}
                    for p in pack.confidence.penalties
                ],
                'quality_scored_layers': pack.confidence.quality_scored_layers,
            },
            'dominant_driver': getattr(pack, 'dominant_driver', None),
            'evidence': getattr(pack, 'evidence', []),
            'recommended_action': getattr(pack, 'recommended_action', None),
            'driver_confidence': getattr(pack, 'driver_confidence', None),
            'action_level': getattr(pack, 'action_level', None)
        }

    # Histogram bundle
    hb = out.histogram_bundle
    histograms = {
        'field': [
            {
                'surface_type': h.surface_type.value,
                'region_id': h.region_id,
                'bin_edges': h.bin_edges,
                'bin_counts': h.bin_counts,
                'mean': h.mean, 'std': h.std,
                'p10': h.p10, 'p90': h.p90,
                'valid_pixels': h.valid_pixels,
                'total_pixels': h.total_pixels,
            }
            for h in hb.field_histograms
        ],
        'zone': [
            {
                'surface_type': h.surface_type.value,
                'region_id': h.region_id,
                'bin_edges': h.bin_edges,
                'bin_counts': h.bin_counts,
                'mean': h.mean, 'std': h.std,
            }
            for h in hb.zone_histograms
        ],
        'delta': [
            {
                'surface_type': d.surface_type.value,
                'date_from': d.date_from,
                'date_to': d.date_to,
                'bin_edges': d.bin_edges,
                'bin_counts': d.bin_counts,
                'mean_change': d.mean_change,
                'shift_direction': d.shift_direction,
            }
            for d in hb.delta_histograms
        ],
        'uncertainty': [
            {
                'surface_type': h.surface_type.value,
                'bin_edges': h.bin_edges,
                'bin_counts': h.bin_counts,
                'mean': h.mean, 'std': h.std,
            }
            for h in hb.uncertainty_histograms
        ],
    }

    # Zones
    zones = []
    for z in out.zone_pack:
        grid_validity = getattr(z, 'grid_validity', 'unknown')
        authority = getattr(z, 'authority', 'algorithmic_scouting_region')
        spatial_geometry_authorized = grid_validity == 'valid' and authority in (
            'management_zone', 'algorithmic_scouting_region'
        )
        zones.append({
            'zone_id': z.zone_id,
            'label': getattr(z, 'description', '') or z.zone_id,
            'zone_type': z.zone_type.value if hasattr(z.zone_type, 'value') else str(z.zone_type),
            'area_fraction': z.area_pct,
            'cell_indices': z.cell_indices if spatial_geometry_authorized else [],
            'severity': z.severity,
            'confidence': z.confidence,
            'top_drivers': z.top_drivers,
            'source_surface_type': getattr(z, 'source_surface_type', ''),
            'linked_actions': z.linked_actions,
            'surface_stats': z.surface_stats,
            'source_dominance': getattr(z, 'source_dominance', None),
            'evidence_age_days': getattr(z, 'evidence_age_days', None),
            'trust_note': getattr(z, 'trust_note', None),
            'is_inferred': getattr(z, 'is_inferred', None),
            'calculation_trace': getattr(z, 'calculation_trace', None),
            'grid_validity': grid_validity,
            'authority': authority,
            'authority_block_reason': getattr(z, 'authority_block_reason', None),
            'spatial_geometry_authorized': spatial_geometry_authorized,
        })

    # Temporal Bundle
    temporal_bundle = None
    tb = getattr(out, 'temporal_bundle', None)
    if tb and tb.slices:
        temporal_bundle = {
            'reference_date': tb.reference_date,
            'lookback_days': tb.lookback_days,
            'lookahead_days': tb.lookahead_days,
            'trend_summary': tb.trend_summary,
            'temporal_quality': tb.temporal_quality,
            'forecast_source': tb.forecast_source,
            'slices': [
                {
                    'date': s.date,
                    'day_offset': s.day_offset,
                    'surface_type': s.surface_type.value,
                    'values': s.values,
                    'is_forecast': s.is_forecast,
                    'confidence': s.confidence,
                    'source': s.source,
                }
                for s in tb.slices
            ],
        }

    # V60B: Ground Truth Registry Summary (pass-through from upstream)
    ground_truth_summary = getattr(out, 'ground_truth_summary', {}) or {}

    resolved_crop_stage, phenology_context = normalize_published_phenology(
        getattr(out, 'resolved_crop_stage', 'UNKNOWN'),
        getattr(out, 'phenology_context', {}) or {},
    )

    return {
        'run_id': out.run_id,
        'publication_run_id': getattr(out, 'publication_run_id', '') or out.run_id,
        'request_run_id': getattr(out, 'request_run_id', ''),
        'publication_id': getattr(out, 'publication_id', ''),
        'publication_status': getattr(out, 'publication_status', 'INVALID_PUBLICATION'),
        'version': getattr(out, 'surface_schema_version', ''),
        'schema_version': getattr(out, 'surface_schema_version', ''),
        'surface_schema_version': getattr(out, 'surface_schema_version', ''),
        'timestamp': out.timestamp,
        'surfaces': surfaces,
        'zones': zones,
        'histograms': histograms,
        'quicklooks': out.quicklooks,
        'raster_pack': out.raster_pack,
        'vector_pack': out.vector_pack,
        'tile_manifest': out.tile_manifest,
        'quality': quality,
        'provenance': out.provenance,
        'resolved_crop_stage': resolved_crop_stage,
        'phenology_context': phenology_context,
        'explainability_pack': explainability_pack,
        'temporal_bundle': temporal_bundle,
        'scenario_pack': getattr(out, 'scenario_pack', []),
        'history_pack': getattr(out, 'history_pack', []),
        'ground_truth_summary': ground_truth_summary,
        'visual_source': getattr(out, 'visual_source', {}) or {},
        'surface_inventory': getattr(out, 'surface_inventory', {}),
        'mode_surface_plan': getattr(out, 'mode_surface_plan', {}),
        # V92.4-BC: Backend-authoritative display state per mode
        'mode_display_state': getattr(out, 'mode_display_state', {}),
        'source_policy_display_state': getattr(out, 'source_policy_display_state', {}),
        'asmae_evidence_state': getattr(out, 'asmae_evidence_state', {}),
        'core_asmae_evidence_state': getattr(out, 'core_asmae_evidence_state', {}) or getattr(out, 'asmae_evidence_state', {}),
        'publication_surface_state': getattr(out, 'publication_surface_state', {}),
        'publication_demotion': getattr(out, 'publication_demotion', {}),
        'asmae_feature_pack': getattr(out, 'asmae_feature_pack', {}),
        'asmae_plot_state_artifact': getattr(out, 'asmae_plot_state_artifact', {}),
        'surface_behavior_proof': getattr(out, 'surface_behavior_proof', {}),
        'display_trace': getattr(out, 'display_trace', {}),
        # Never emit an empty asmae_proof — use canonical default when missing
        'asmae_proof': getattr(out, 'asmae_proof', None) if getattr(out, 'asmae_proof', None) and isinstance(getattr(out, 'asmae_proof', None), dict) and len(getattr(out, 'asmae_proof', None)) > 0 else build_default_asmae_proof(),
        "render_authorizations": getattr(out, "render_authorizations", {}) or build_no_data_render_authorizations(),
        "render_authorization_version": getattr(out, "render_authorization_version", ""),
    }


def main():
    parser = argparse.ArgumentParser(description='Layer 10 Frontend Bridge')
    parser.add_argument('--context', type=str, required=True, help='Base64-encoded JSON context')
    args = parser.parse_args()

    try:
        ctx = json.loads(base64.b64decode(args.context).decode('utf-8'))
    except Exception:
        try:
            ctx = json.loads(args.context)
        except Exception as e:
            print(json.dumps({'error': f'Invalid context: {e}'}))
            sys.exit(1)

    try:
        inp = build_input_from_context(ctx)
        out = run_layer10_sire(inp)
        result = serialize_output(out)
        result['plot_id'] = inp.plot_id
        result['grid'] = {'height': inp.grid_height, 'width': inp.grid_width}
        print(json.dumps(result, default=str))
    except Exception as e:
        import traceback
        print(json.dumps({'error': str(e), 'traceback': traceback.format_exc()}))
        sys.exit(1)


if __name__ == '__main__':
    main()
