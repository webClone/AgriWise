import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from layer9_interface.schema import Layer9Input
from layer9_interface.reporting.schemas import EvidenceItem, ClassifiedEvidence

@dataclass(frozen=True)
class ReportEvidencePacket:
    plot_id: str
    evidence_window: Dict[str, Optional[str]]
    raw_items: List[EvidenceItem]
    classified_items: List[ClassifiedEvidence]
    provenance_hashes: Dict[str, Optional[str]]
    source_file_hashes: Dict[str, str]
    data_completeness: float
    limitations: List[str]

def get_file_sha256(path: Path) -> str:
    """Helper to get file sha256 hash securely and deterministically."""
    if not path.exists():
        return "not_found"
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "read_error"

def compile_evidence(l9_input: Layer9Input) -> ReportEvidencePacket:
    # Deep-copy input to prevent side-effect mutations
    input_copy = copy.deepcopy(l9_input)
    
    plot_id = input_copy.plot_id or "UNKNOWN"
    limitations = []
    
    raw_items: List[EvidenceItem] = []
    source_file_hashes: Dict[str, str] = {}
    provenance_hashes: Dict[str, Optional[str]] = {
        "layer0_output_hash": None,
        "asmae_content_hash": None,
        "asmae_artifact_instance_hash": None,
        "memory_content_hash": None,
        "dataset_hash": None,
        "model_registry_hash": None,
    }

    # Extract window from biophysical history if available
    window_start = None
    window_end = None
    bio_hist = input_copy.biophysical_history or {}
    if "last_14d_weather" in bio_hist and bio_hist["last_14d_weather"]:
        weather_list = bio_hist["last_14d_weather"]
        if isinstance(weather_list, list) and len(weather_list) > 0:
            # Assume elements have timestamps
            dates = [w.get("timestamp") for w in weather_list if isinstance(w, dict) and w.get("timestamp")]
            if dates:
                window_start = min(dates)
                window_end = max(dates)
                
    evidence_window = {
        "start_date": window_start,
        "end_date": window_end
    }

    # Gather data completeness indicators (L1, L2, L3, L6, L10 presence)
    expected_sources = ["L0_hashes", "L1_fusion", "L2_veg", "L3_diag", "L10_sire"]
    actual_sources = []
    
    # 1. Layer 0 telemetry/hashes
    if input_copy.audit_grade:
        actual_sources.append("L0_hashes")
        raw_items.append(EvidenceItem(
            evidence_id="L0_audit_grade",
            source_layer="L0",
            source_type="telemetry",
            variable="audit_grade",
            value=input_copy.audit_grade,
            confidence=1.0,
            uncertainty=0.0,
            provenance_hash=hashlib.sha256(input_copy.audit_grade.encode()).hexdigest()
        ))
    
    # 2. Layer 1 Fused Telemetry
    l1_data = input_copy.l1_fusion_data or {}
    if l1_data:
        actual_sources.append("L1_fusion")
        ev_items = l1_data.get("evidence_items", [])
        for i, item in enumerate(ev_items):
            raw_items.append(EvidenceItem(
                evidence_id=item.get("evidence_id") or f"L1_evidence_{i}",
                source_layer="L1",
                source_type="sensor" if item.get("observation_type") == "measurement" else "model",
                variable=item.get("variable", "unknown"),
                value=item.get("value"),
                confidence=item.get("confidence", 0.5),
                uncertainty=1.0 - item.get("confidence", 0.5),
                provenance_hash=item.get("evidence_id") or f"L1_hash_{i}"
            ))

    # 3. Layer 2 Vegetation stress
    l2_data = input_copy.l2_vegetation_data or {}
    if l2_data:
        actual_sources.append("L2_veg")
        if (
            l2_data.get("phenology_receipt_valid") is True
            and l2_data.get("stage") not in {None, "UNKNOWN"}
        ):
            confidence = max(0.0, min(1.0, float(l2_data.get("phenology_confidence") or 0.0)))
            raw_items.append(EvidenceItem(
                evidence_id="L2_phenology_stage",
                source_layer="L2",
                source_type="model",
                variable="phenology_stage",
                value=l2_data["stage"],
                confidence=confidence,
                uncertainty=1.0 - confidence,
                provenance_hash=l2_data["phenology_posterior_hash"],
            ))

    # 4. Layer 3 Diagnostics
    if input_copy.diagnoses:
        actual_sources.append("L3_diag")
        for i, d in enumerate(input_copy.diagnoses):
            prob = d.get("probability", 0.0)
            raw_items.append(EvidenceItem(
                evidence_id=f"L3_diagnosis_{d.get('problem_id', 'unknown')}",
                source_layer="L3",
                source_type="model",
                variable=d.get("problem_id", "unknown"),
                value=prob,
                confidence=d.get("confidence", 0.5),
                uncertainty=1.0 - d.get("confidence", 0.5),
                provenance_hash=hashlib.sha256(str(d).encode()).hexdigest()
            ))

    # 5. Layer 6 Yield / Economics
    l6_data = input_copy.l6_execution_data or {}
    if l6_data:
        actual_sources.append("L6_execution")
        for k, v in l6_data.items():
            if isinstance(v, (int, float)):
                raw_items.append(EvidenceItem(
                    evidence_id=f"L6_metric_{k}",
                    source_layer="L6",
                    source_type="model",
                    variable=k,
                    value=v,
                    confidence=0.85,
                    uncertainty=0.15,
                    provenance_hash=hashlib.sha256(f"{k}:{v}".encode()).hexdigest()
                ))

    # 6. Layer 10 surfaces/provenance hashes
    l10_data = input_copy.l10_sire_data or {}
    if l10_data:
        actual_sources.append("L10_sire")
        surfs = l10_data.get("surfaces", [])
        for i, s in enumerate(surfs):
            prov = s.get("provenance", {})
            if prov:
                # Capture BMA/sire provenance hashes
                for key in provenance_hashes:
                    if prov.get(key) and not provenance_hashes[key]:
                        provenance_hashes[key] = prov.get(key)
                
                # Check for shadow ML expert outputs
                if prov.get("asmae_channel") == "shadow_ml":
                    raw_items.append(EvidenceItem(
                        evidence_id=s.get("surface_id") or f"L10_shadow_ml_{i}",
                        source_layer="L10",
                        source_type="ml",
                        variable=s.get("semantic_type", "shadow_ml"),
                        value=prov.get("value"),
                        confidence=prov.get("confidence", 0.5),
                        uncertainty=prov.get("uncertainty", 0.5),
                        provenance_hash=prov.get("model_registry_hash") or "shadow_ml_provenance",
                        extra_metadata={"asmae_channel": "shadow_ml", "model_id": prov.get("model_id")}
                    ))
                
                # Check for visual-only/uncertified 1m
                res = prov.get("resolution_m", 10.0)
                if res <= 1.0:
                    raw_items.append(EvidenceItem(
                        evidence_id=s.get("surface_id") or f"L10_visual_1m_{i}",
                        source_layer="L10",
                        source_type="inferred_detail",
                        variable=s.get("semantic_type", "visual_resolution"),
                        value="visual_1m_detail",
                        confidence=prov.get("confidence", 0.5),
                        uncertainty=prov.get("uncertainty", 0.5),
                        provenance_hash=prov.get("layer0_output_hash") or "visual_1m_provenance",
                        extra_metadata={
                            "resolution_m": res,
                            "certification_source": prov.get("certification_source"),
                            "certification_status": prov.get("certification_status"),
                            "certification_id": prov.get("certification_id")
                        }
                    ))

    # 7. V86 validation ledger (read-only file read)
    try:
        from rollout.rollout_config import VALIDATION_LEDGER_PATH
        ledger_path = VALIDATION_LEDGER_PATH
        if ledger_path and Path(ledger_path).exists():
            source_file_hashes["validation_ledger"] = get_file_sha256(Path(ledger_path))
            
            # 1st pass: build run_id to validation status map
            run_id_to_status = {}
            with open(ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    rec_run_id = rec.get("run_id")
                    if not rec_run_id:
                        continue
                    rec_type = rec.get("record_type", "asmae_run")
                    if rec_type == "asmae_run":
                        status = rec.get("validation", {}).get("manual_validation_status", "pending")
                        run_id_to_status[rec_run_id] = status
                    elif rec_type == "candidate_update":
                        status = rec.get("learning_candidate_status", "pending")
                        run_id_to_status[rec_run_id] = status

            # 2nd pass: compile evidence items
            with open(ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("plot_id") == plot_id:
                            rec_type = rec.get("record_type")
                            rec_run_id = rec.get("run_id")
                            run_status = run_id_to_status.get(rec_run_id, "pending") if rec_run_id else "pending"
                            
                            if rec_type == "validation_event":
                                raw_items.append(EvidenceItem(
                                    evidence_id=rec.get("event_id") or f"ledger_event_{rec.get('timestamp')}",
                                    source_layer="validation_ledger",
                                    source_type=rec.get("source_type", "unknown"),
                                    variable=rec.get("target_variable", "unknown"),
                                    value=rec.get("observed_value"),
                                    confidence=rec.get("confidence", 1.0),
                                    uncertainty=1.0 - rec.get("confidence", 1.0),
                                    provenance_hash=hashlib.sha256(line.encode()).hexdigest(),
                                    timestamp=rec.get("timestamp"),
                                    extra_metadata={
                                        "record_type": "validation_event",
                                        "manual_validation_status": run_status,
                                        "record": rec
                                    }
                                ))
                            else:
                                raw_items.append(EvidenceItem(
                                    evidence_id=rec.get("run_id") or f"ledger_{rec.get('timestamp')}",
                                    source_layer="validation_ledger",
                                    source_type="ledger",
                                    variable=rec_type or "asmae_run",
                                    value=rec.get("validation", {}).get("manual_validation_status") or rec.get("learning_candidate_status") or rec_type or "asmae_run",
                                    confidence=1.0,
                                    uncertainty=0.0,
                                    provenance_hash=hashlib.sha256(line.encode()).hexdigest(),
                                    timestamp=rec.get("timestamp"),
                                    extra_metadata={
                                        "record_type": rec_type or "asmae_run",
                                        "manual_validation_status": run_status,
                                        "record": rec
                                    }
                                ))
                    except Exception:
                        continue
    except Exception as e:
        limitations.append(f"Failed to read validation ledger: {str(e)}")

    # 8. V87 plot memory (read-only file read)
    try:
        # Resolve geom/season to load memory
        geom = l10_data.get("geometry_hash")
        season = l10_data.get("crop_season_id")
        if not geom and l1_data:
            geom = l1_data.get("geometry_hash")
        
        if plot_id != "UNKNOWN" and geom and season:
            from asmae_learn.plot_memory import load_plot_memory
            mem = load_plot_memory(plot_id, geom, season)
            if mem:
                # Update memory content hash in provenance hashes if found
                if mem.memory_content_hash:
                    provenance_hashes["memory_content_hash"] = mem.memory_content_hash
                
                # Check target variables
                for var, var_data in mem.variables.items():
                    raw_items.append(EvidenceItem(
                        evidence_id=f"memory_{var}",
                        source_layer="plot_memory",
                        source_type="memory",
                        variable=var,
                        value=var_data.get("value"),
                        confidence=var_data.get("confidence", 0.5),
                        uncertainty=1.0 - var_data.get("confidence", 0.5),
                        provenance_hash=mem.memory_content_hash,
                        extra_metadata={"memory_status": mem.memory_status, "trust": var_data.get("trust")}
                    ))
    except Exception as e:
        limitations.append(f"Failed to read plot memory: {str(e)}")

    # Calculate data completeness
    completeness = len(actual_sources) / len(expected_sources) if expected_sources else 0.0

    return ReportEvidencePacket(
        plot_id=plot_id,
        evidence_window=evidence_window,
        raw_items=raw_items,
        classified_items=[],  # populated by classifier
        provenance_hashes=provenance_hashes,
        source_file_hashes=source_file_hashes,
        data_completeness=completeness,
        limitations=limitations
    )
