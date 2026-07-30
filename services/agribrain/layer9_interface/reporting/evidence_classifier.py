from typing import Any, List, Optional
from layer9_interface.reporting.schemas import EvidenceItem, ClassifiedEvidence

APPROVED_EXTERNAL_VALIDATION_SOURCES = {
    "agronomist_observation", "soil_lab", "calibrated_sensor", 
    "farmer_observation", "field_scout", "drone_image", 
    "farmer_photo", "harvest_record", "insurance_inspection"
}

from certification.v90_resolver import verify_v90_certification_record

class EvidenceClassifier:
    def __init__(self, certification_resolver=None):
        self.certification_resolver = certification_resolver or verify_v90_certification_record

    def classify_item(self, item: EvidenceItem) -> ClassifiedEvidence:
        tier = "unknown"
        admissibility = "excluded"
        can_support_claim = False
        can_support_investor_metric = False
        can_support_government_aggregate = False
        exclusion_reasons = []
        certification_reason_codes = []
        
        validation_status = "none"
        certification_status = None
        
        # 1. Check for shadow ML diagnostic
        is_ml = (
            item.source_layer == "L10" and 
            (item.source_type == "ml" or item.extra_metadata.get("asmae_channel") == "shadow_ml")
        )
        # 2. Check for weak label
        is_weak_label = item.extra_metadata.get("is_weak_label", False) or item.variable == "weak_label"
        
        # 3. Check for Layer 8 prescriptive action
        is_l8_action = item.source_layer == "L8" or item.source_type == "prescriptive_action" or "action" in item.variable.lower()
        
        # 4. Check for high resolution visual details (resolution_m <= 1.0)
        is_high_res = (
            item.source_type == "inferred_detail" or 
            item.extra_metadata.get("resolution_m", 10.0) <= 1.0
        )

        if is_ml:
            tier = "shadow_ml_diagnostic"
            admissibility = "diagnostic"
            exclusion_reasons.append("Shadow ML is diagnostic-only and not institutional proof.")
        elif is_weak_label:
            tier = "weak_label"
            admissibility = "excluded"
            exclusion_reasons.append("Weak label cannot be used as institutional proof.")
        elif is_l8_action:
            tier = "prescriptive_action"
            admissibility = "excluded"
            exclusion_reasons.append("Layer 8 actions are prescriptive and not validation evidence.")
        elif is_high_res:
            # Check certification gate for V90
            cert_src = item.extra_metadata.get("certification_source")
            cert_status = item.extra_metadata.get("certification_status")
            cert_id = item.extra_metadata.get("certification_id")
            
            source_hashes = item.extra_metadata.get("source_hashes")
            if not source_hashes:
                source_hashes = {
                    "layer0_output_hash": item.extra_metadata.get("layer0_output_hash", ""),
                    "asmae_content_hash": item.extra_metadata.get("asmae_content_hash", ""),
                    "asmae_artifact_instance_hash": item.extra_metadata.get("asmae_artifact_instance_hash", ""),
                    "memory_content_hash": item.extra_metadata.get("memory_content_hash", ""),
                    "report_verified_evidence_hash": item.extra_metadata.get("report_verified_evidence_hash", ""),
                }
            
            time_window = item.extra_metadata.get("time_window")
            if not time_window:
                time_window = (
                    item.extra_metadata.get("time_window_start"),
                    item.extra_metadata.get("time_window_end")
                )

            # Use dependency injected resolver
            res = self.certification_resolver(
                certification_id=cert_id,
                plot_id=item.extra_metadata.get("plot_id") or item.extra_metadata.get("plot"),
                variable=item.variable,
                time_window=time_window,
                geometry_hash=item.extra_metadata.get("geometry_hash"),
                crop_season_id=item.extra_metadata.get("crop_season_id"),
                source_hashes=source_hashes
            )
            is_verified = res.approved if hasattr(res, "approved") else bool(res)
            if res and hasattr(res, "reason_codes"):
                certification_reason_codes = res.reason_codes
            
            if cert_src == "v90" and cert_status == "certified" and cert_id and is_verified:
                tier = "certified_1m_inferred_detail"
                admissibility = "supporting"
                certification_status = "certified"
                can_support_claim = True
                can_support_investor_metric = True
                can_support_government_aggregate = True
            else:
                if cert_src == "v90" and cert_status == "certified" and cert_id:
                    tier = "uncertified_1m"
                else:
                    tier = "visual_only_1m"
                admissibility = "excluded"
                exclusion_reasons.append("Visual-only 1m details are uncertified and excluded from proof.")
        elif item.source_layer == "validation_ledger":
            rec_type = item.extra_metadata.get("record_type")
            manual_status = item.extra_metadata.get("manual_validation_status", "pending")
            
            # In V89.1, check exact blockers
            check_failed = False
            
            if rec_type != "validation_event":
                exclusion_reasons.append("not_validation_event")
                check_failed = True
            if manual_status != "approved":
                exclusion_reasons.append("manual_validation_not_approved")
                check_failed = True
            if item.source_type not in APPROVED_EXTERNAL_VALIDATION_SOURCES:
                exclusion_reasons.append("source_type_not_external_validation")
                check_failed = True
            if item.value is None:
                exclusion_reasons.append("missing_observed_value")
                check_failed = True
            if not item.variable or item.variable == "unknown":
                exclusion_reasons.append("missing_target_variable")
                check_failed = True
                
            rec_dict = item.extra_metadata.get("record") or {}
            if not rec_dict.get("event_id"):
                exclusion_reasons.append("missing_event_id")
                check_failed = True
                
            if not check_failed:
                tier = "validated_field_evidence"
                admissibility = "proof"
                validation_status = "approved"
                can_support_claim = True
                can_support_investor_metric = True
                can_support_government_aggregate = True
            else:
                tier = "unapproved_validation" if rec_type == "validation_event" else "ledger_metadata"
                admissibility = "supporting" if rec_type == "asmae_run" else "excluded"
                validation_status = manual_status
        elif item.source_layer == "plot_memory":
            tier = "certified_plot_memory"
            admissibility = "supporting"
            certification_status = item.extra_metadata.get("memory_status")
            can_support_claim = False
            can_support_investor_metric = True
            can_support_government_aggregate = True
        elif item.source_layer == "L0":
            tier = "verified_observation"
            admissibility = "proof"
            can_support_claim = True
            can_support_investor_metric = True
            can_support_government_aggregate = True
        elif item.source_layer == "L1" and item.source_type == "sensor":
            tier = "verified_observation"
            admissibility = "proof"
            can_support_claim = True
            can_support_investor_metric = True
            can_support_government_aggregate = True
        elif item.source_layer == "L1" and item.source_type == "model":
            tier = "physics_model_output"
            admissibility = "supporting"
            can_support_investor_metric = True
            can_support_government_aggregate = True
        elif item.source_layer in ("L2", "L3", "L10"):
            tier = "physics_model_output"
            admissibility = "supporting"
            can_support_investor_metric = True
            can_support_government_aggregate = True
        elif item.source_layer in ("L6", "forecast"):
            tier = "forecast"
            admissibility = "supporting"
            can_support_investor_metric = True
        else:
            tier = "physics_model_output"
            admissibility = "supporting"
            can_support_investor_metric = True
            can_support_government_aggregate = True

        return ClassifiedEvidence(
            evidence_id=item.evidence_id,
            tier=tier,
            institutional_admissibility=admissibility,
            source_layer=item.source_layer,
            source_type=item.source_type,
            variable=item.variable,
            value=item.value,
            confidence=item.confidence,
            uncertainty=item.uncertainty,
            validation_status=validation_status,
            certification_status=certification_status,
            can_support_claim=can_support_claim,
            can_support_investor_metric=can_support_investor_metric,
            can_support_government_aggregate=can_support_government_aggregate,
            exclusion_reasons=exclusion_reasons,
            provenance_hash=item.provenance_hash,
            certification_reason_codes=certification_reason_codes
        )

default_classifier = EvidenceClassifier()

def classify_evidence_item(item: EvidenceItem, resolver=None) -> ClassifiedEvidence:
    if resolver is not None:
        return EvidenceClassifier(certification_resolver=resolver).classify_item(item)
    return default_classifier.classify_item(item)

def classify_evidence_packet(items: List[EvidenceItem], resolver=None) -> List[ClassifiedEvidence]:
    if resolver is not None:
        classifier = EvidenceClassifier(certification_resolver=resolver)
    else:
        classifier = default_classifier
    return [classifier.classify_item(item) for item in items]
