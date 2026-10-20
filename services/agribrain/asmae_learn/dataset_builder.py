from __future__ import annotations
try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from rollout.rollout_config import VALIDATION_LEDGER_PATH

REQUIRED_LINEAGE_FIELDS = [
    "plot_id",
    "run_id",
    "geometry_hash",
    "layer0_output_hash",
    "asmae_content_hash",
    "asmae_artifact_instance_hash",
]

def compute_dataset_hash(samples: List[Dict[str, Any]]) -> str:
    # Sort samples by run_id + target_variable to be fully deterministic
    sorted_samples = sorted(samples, key=lambda s: (s.get("run_id", ""), s.get("target_variable", "")))
    serialized = json.dumps(sorted_samples, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()

def build_validated_training_view(ledger_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = Path(ledger_path) if ledger_path else VALIDATION_LEDGER_PATH
    if not path.exists():
        return []

    # Map of run_id -> replayed state
    runs: Dict[str, Dict[str, Any]] = {}
    # Track revoked plot/geom/seasons
    revoked_plot_geom_seasons = set()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            r_id = rec.get("run_id")
            rec_type = rec.get("record_type")

            if rec_type == "memory_revocation":
                p_id = rec.get("plot_id")
                old_geom = rec.get("old_geometry_hash")
                old_season = rec.get("old_crop_season_id")
                if p_id and old_geom and old_season:
                    revoked_plot_geom_seasons.add((p_id, old_geom, old_season))
                continue

            if not r_id:
                continue

            if r_id not in runs:
                runs[r_id] = {
                    "run_id": r_id,
                    "validation_events": [],
                    "latest_candidate_status": "pending",
                    "eligible_for_asmae_learn": False,
                    "disagreement_report": None,
                    "memory_revoked": False,
                }

            run_view = runs[r_id]

            if rec_type == "asmae_run":
                # Merge main run info
                run_view.update(rec)
            elif rec_type == "validation_event":
                run_view["validation_events"].append(rec)
            elif rec_type == "disagreement_report":
                run_view["disagreement_report"] = rec
            elif rec_type == "candidate_update":
                run_view["latest_candidate_status"] = rec.get("learning_candidate_status")
                run_view["eligible_for_asmae_learn"] = rec.get("eligible_for_asmae_learn", False)
                if "candidate" in rec:
                    run_view["candidate"] = rec["candidate"]

    samples = []
    for r_id, run_view in runs.items():
        # Enforce all required V88 builder checks:
        
        # 1. Candidate must be approved and eligible for learning
        if run_view.get("latest_candidate_status") != "approved":
            continue
        if not run_view.get("eligible_for_asmae_learn"):
            continue

        # 2. Check if revoked or memory revocation affected it
        p_id = run_view.get("plot_id")
        geom = run_view.get("geometry_hash")
        season = run_view.get("crop_season_id") or run_view.get("crop_context", {}).get("crop_season_id") or "default_season"
        if (p_id, geom, season) in revoked_plot_geom_seasons:
            continue

        # 3. No later contradiction (agreement_score must not indicate rejection)
        diag = run_view.get("disagreement_report")
        if diag and diag.get("candidate_status") == "rejected":
            continue

        # 4. Exclude weak labels, visual-only 1m, Layer 8 actions
        if run_view.get("weak_labels_as_ground_truth") or run_view.get("validation", {}).get("use_weak_labels_as_ground_truth"):
            continue
        
        res_m = run_view.get("diagnostics", {}).get("resolution_selected_m") or run_view.get("resolution_m", 10.0)
        if res_m <= 1.0 or run_view.get("visual_only") or run_view.get("diagnostics", {}).get("visual_only"):
            continue
            
        if run_view.get("diagnostic_only") or run_view.get("diagnostics", {}).get("diagnostic_only"):
            continue

        # Check for Layer 8 actions / target variables
        target_var = None
        events = run_view.get("validation_events", [])
        if events:
            target_var = events[0].get("target_variable")
        if not target_var and "candidate" in run_view:
            target_var = run_view["candidate"].get("target_variable")

        if target_var in ("yield ground truth", "1m certification", "biotic outbreak confirmation", "irreversible action success", "layer8_action_success"):
            continue

        # 5. Must have lineage hashes
        has_lineage = True
        for f in REQUIRED_LINEAGE_FIELDS:
            if not run_view.get(f):
                has_lineage = False
                break
        if not has_lineage:
            continue

        # 6. Extract Target Label: Must come strictly from external validation
        # target_value must come from external validation event, approved manual event
        if not events:
            continue
        
        event = events[0]
        
        VALID_SOURCE_TYPES = {
            "agronomist_observation",
            "soil_lab",
            "calibrated_sensor",
            "farmer_observation",
            "drone_image",
            "farmer_photo",
            "irrigation_log",
            "harvest_record",
            "insurance_inspection",
            "field_scout",
        }
        
        source_type = event.get("source_type")
        if source_type not in VALID_SOURCE_TYPES:
            continue
        
        target_value = event.get("observed_value")
        target_confidence = event.get("confidence")

        # Explicitly exclude ASMAE or BMA consensus alone as ground truth labels
        if target_value is None or target_confidence is None:
            continue

        fin_conf = finite_real(target_confidence)
        if fin_conf is None or fin_conf <= 0.0:
            continue

        CONTINUOUS_VARS = {"vigor", "canopy_water", "salinity_stress", "yield_observed"}
        if target_var in CONTINUOUS_VARS:
            fin_val = finite_real(target_value)
            if fin_val is None:
                continue
            target_value = fin_val

        target_confidence = fin_conf

        validation_event_ids = [e.get("event_id") for e in events if e.get("event_id")]
        disagreement_report_hash = run_view.get("candidate", {}).get("disagreement_report_hash", "")
        candidate_id = run_view.get("candidate", {}).get("candidate_id")
        candidate_type = run_view.get("candidate", {}).get("candidate_type")

        # Strict Lineage Completeness Gates (V88.1)
        if not validation_event_ids:
            continue
        if not disagreement_report_hash or not isinstance(disagreement_report_hash, str) or disagreement_report_hash.strip() == "":
            continue
        if not candidate_id or not isinstance(candidate_id, str) or candidate_id.strip() == "":
            continue
        if not candidate_type or not isinstance(candidate_type, str) or candidate_type.strip() == "":
            continue
        if not target_var or not isinstance(target_var, str) or target_var.strip() == "":
            continue

        # Get memory content hash if memory-derived
        memory_content_hash = run_view.get("memory", {}).get("memory_content_hash") or run_view.get("memory_content_hash", "")

        sample = {
            "plot_id": p_id,
            "run_id": r_id,
            "geometry_hash": geom,
            "layer0_output_hash": run_view["layer0_output_hash"],
            "asmae_content_hash": run_view["asmae_content_hash"],
            "asmae_artifact_instance_hash": run_view["asmae_artifact_instance_hash"],
            "memory_content_hash": memory_content_hash,
            "validation_event_ids": validation_event_ids,
            "disagreement_report_hash": disagreement_report_hash,
            "candidate_id": candidate_id,
            "candidate_type": candidate_type,
            "target_variable": target_var,
            "target_value": target_value,
            "target_confidence": target_confidence,
        }
        samples.append(sample)

    return samples

def split_dataset_plot_disjoint(
    samples: List[Dict[str, Any]],
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    if abs(train_ratio + validation_ratio + test_ratio - 1.0) > 1e-9:
        raise ValueError("ratios_must_sum_to_one")
        
    # Group samples by plot_id
    plot_groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in samples:
        plot_groups.setdefault(s["plot_id"], []).append(s)
        
    # Sort plots to ensure deterministic splits
    sorted_plots = sorted(plot_groups.keys())
    n_plots = len(sorted_plots)
    
    # We need a minimum number of plots to split them disjointly
    if n_plots < 3:
        raise ValueError("dataset_too_small_for_valid_holdout")

    # Distribute plots to train, validation, test
    # A simple deterministic round-robin or bucket split
    train_plots = []
    val_plots = []
    test_plots = []
    
    # Let's split plots strictly so each plot is in only one set
    for i, plot_id in enumerate(sorted_plots):
        pct = i / n_plots
        if pct < train_ratio:
            train_plots.append(plot_id)
        elif pct < train_ratio + validation_ratio:
            val_plots.append(plot_id)
        else:
            test_plots.append(plot_id)

    # In case any list is empty, adjust to ensure train/val/test are not empty if n_plots >= 3
    if not val_plots and len(test_plots) > 1:
        val_plots.append(test_plots.pop())
    elif not val_plots and len(train_plots) > 1:
        val_plots.append(train_plots.pop())
    if not test_plots and len(train_plots) > 1:
        test_plots.append(train_plots.pop())

    train_set = []
    val_set = []
    test_set = []
    
    for plot_id in train_plots:
        train_set.extend(plot_groups[plot_id])
    for plot_id in val_plots:
        val_set.extend(plot_groups[plot_id])
    for plot_id in test_plots:
        test_set.extend(plot_groups[plot_id])

    # Enforce time-disjoint split within each group if needed (chronological sorting is already preserved by processing order)
    # Re-sort lists chronologically by run_id/timestamp
    train_set = sorted(train_set, key=lambda s: s.get("run_id", ""))
    val_set = sorted(val_set, key=lambda s: s.get("run_id", ""))
    test_set = sorted(test_set, key=lambda s: s.get("run_id", ""))

    return train_set, val_set, test_set
