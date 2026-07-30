import os
from typing import Dict, Optional, Any
from layer9_interface.schema import Layer9Input

def gather_provenance(
    l9_input: Layer9Input,
    report_input_hash: str,
    verified_evidence_hash: str,
    report_content_hash: str = "",
    report_instance_hash: str = ""
) -> Dict[str, Optional[str]]:
    """Gathers hashes across Layer 0, ASMAE, memory, registry, and reports."""
    provenance = {
        "layer0_output_hash": None,
        "asmae_content_hash": None,
        "asmae_artifact_instance_hash": None,
        "memory_content_hash": None,
        "dataset_hash": None,
        "model_registry_hash": None,
        "report_input_hash": report_input_hash,
        "verified_evidence_hash": verified_evidence_hash,
        "report_content_hash": report_content_hash,
        "report_instance_hash": report_instance_hash,
    }

    # Extract from Layer 10 SIRE data
    l10_data = l9_input.l10_sire_data or {}
    if isinstance(l10_data, dict):
        # Check surfaces
        surfs = l10_data.get("surfaces", [])
        for s in surfs:
            prov = s.get("provenance", {}) if isinstance(s, dict) else {}
            if prov:
                for k in ["layer0_output_hash", "asmae_content_hash", "asmae_artifact_instance_hash", "model_registry_hash", "dataset_hash"]:
                    if prov.get(k) and not provenance.get(k):
                        provenance[k] = prov.get(k)

    # Extract from Layer 1 fusion data
    l1_data = l9_input.l1_fusion_data or {}
    if isinstance(l1_data, dict):
        for k in ["layer0_output_hash", "asmae_content_hash", "asmae_artifact_instance_hash"]:
            if l1_data.get(k) and not provenance.get(k):
                provenance[k] = l1_data.get(k)

    # Extract from plot DNA / memory if not populated
    plot_dna = l9_input.plot_dna or {}
    if isinstance(plot_dna, dict) and plot_dna.get("memory_content_hash") and not provenance["memory_content_hash"]:
        provenance["memory_content_hash"] = plot_dna.get("memory_content_hash")

    return provenance
