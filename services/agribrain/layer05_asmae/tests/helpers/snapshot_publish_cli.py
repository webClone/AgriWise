"""CLI helper to execute canonical plot snapshot publication in a separate OS process."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store
from services.agribrain.layer05_asmae.plot_snapshot_store import publish_canonical_plot_snapshot
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash


def build_payload(
    plot_id: str,
    tenant_id: str,
    farm_id: str,
    crop_cycle_id: str,
    snapshot_id: str,
    job_id: str,
    manifest_hash: str,
    root_moisture: float,
    canopy_vigor: float,
):
    states = {
        "root_zone_moisture": float(root_moisture),
        "canopy_vigor": float(canopy_vigor),
        "canopy_water_content": 0.420,
        "evapotranspiration_actual": 3.85,
    }
    sigmas = {
        "root_zone_moisture": 0.012,
        "canopy_vigor": 0.015,
        "canopy_water_content": 0.018,
        "evapotranspiration_actual": 0.25,
    }
    vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)
    num_rec = {
        "states": states,
        "sigmas": sigmas,
        "numerical_vector_hash": vec_hash,
    }
    asmae_result = {
        "plot_id": plot_id,
        "snapshot_id": snapshot_id,
        "content_hash": hashlib.sha256(f"content-{snapshot_id}".encode()).hexdigest(),
        "crop_posterior_lineage": "lineage-citrus-mitidja-v1",
        "crop_worldline_event_id": "event-wl-crop-101",
        "phenology_worldline_event_id": "event-wl-phen-101",
        "crop_influence_manifest_hash": manifest_hash,
        "crop_evidence_ledger_hash": "ledger-hash-101",
        "asmae_posterior_numerical_record": num_rec,
        "asmae_numerical_digest": vec_hash,
        "claims_numerical_authority": True,
        "state_means": states,
        "sigmas": sigmas,
        "raster_maps": {},
    }
    frontend = {
        "version": SURFACES_SCHEMA_VERSION,
        "surface_schema_version": SURFACES_SCHEMA_VERSION,
        "intelligence_snapshot_id": snapshot_id,
        "plot_id": plot_id,
        "tenant_id": tenant_id,
        "farm_id": farm_id,
        "publication_id": f"pub-{snapshot_id}",
        "publication_run_id": f"run-{snapshot_id}",
        "run_id": f"run-{snapshot_id}",
        "pipeline_state": "terminal_layer10_published",
        "publication_status": "VALID_NORMAL",
        "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
        "render_authorizations": {"canopy": {"authorized": True}},
        "claims_numerical_authority": True,
        "asmae_posterior_numerical_record": num_rec,
        "asmae_proof": {
            "proof_id": f"proof-{snapshot_id}",
            "status": "valid",
            "numerical_vector_hash": vec_hash,
        },
        "scientific_evidence_lineage": {
            "crop_posterior_lineage": "lineage-citrus-mitidja-v1",
            "crop_worldline_event_id": "event-wl-crop-101",
            "phenology_worldline_event_id": "event-wl-phen-101",
            "asmae_posterior_vector_hash": vec_hash,
            "replay_mode": "exact_frozen_worldline_events",
        },
        "surfaces": [
            {
                "surface_id": "surface-canopy-vigor",
                "surface_type": "canopy_vigor",
                "values": [[canopy_vigor]],
                "resolution_m": 10.0,
                "content_hash": hashlib.sha256(b"surf-vigor").hexdigest(),
            }
        ],
        "crop_cycle_id": crop_cycle_id,
    }
    return asmae_result, frontend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--plot-id", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--farm-id", required=True)
    parser.add_argument("--geometry-hash", required=True)
    parser.add_argument("--crop-cycle-id", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--manifest-hash", required=True)
    parser.add_argument("--root-moisture", type=float, default=0.382)
    parser.add_argument("--canopy-vigor", type=float, default=0.615)
    args = parser.parse_args()

    plot_snapshot_store.PLOT_SNAPSHOT_ROOT = Path(args.root)

    ns = PlotNamespace(
        tenant_id=args.tenant_id,
        farm_id=args.farm_id,
        plot_id=args.plot_id,
    )

    asmae_result, frontend = build_payload(
        plot_id=args.plot_id,
        tenant_id=args.tenant_id,
        farm_id=args.farm_id,
        crop_cycle_id=args.crop_cycle_id,
        snapshot_id=args.snapshot_id,
        job_id=args.job_id,
        manifest_hash=args.manifest_hash,
        root_moisture=args.root_moisture,
        canopy_vigor=args.canopy_vigor,
    )

    try:
        head = publish_canonical_plot_snapshot(
            namespace=ns,
            plot_id=args.plot_id,
            tenant_id=args.tenant_id,
            farm_id=args.farm_id,
            geometry_hash=args.geometry_hash,
            snapshot_id=args.snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id=args.job_id,
            manifest_hash=args.manifest_hash,
            execution_identity={"crop_cycle_id": args.crop_cycle_id},
            allow_overwrite=False,
        )
        print(f"OK:{head.get('node_hash')}:{head.get('frontend_publication_hash')}")
        sys.exit(0)
    except ValueError as exc:
        if "collision" in str(exc).lower():
            print(f"COLLISION:{exc}")
            sys.exit(2)
        print(f"VALUE_ERROR:{exc}")
        sys.exit(3)
    except Exception as exc:
        print(f"ERROR:{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
