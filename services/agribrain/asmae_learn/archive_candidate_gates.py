"""
Archive Candidate Promotion Gates.
Enforces the mandatory requirement of independent external validation (e.g. V86)
before promoting historical archive candidates to the ASMAE-Learn active memory system.
"""
from typing import Optional, Tuple
from .archive_candidates import ArchiveMemoryCandidate

class ArchiveCandidateGate:
    def __init__(self):
        pass

    def evaluate_promotion(
        self,
        candidate: ArchiveMemoryCandidate,
        external_validation_ref: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Determines whether an archive parameter candidate is allowed to be promoted to active memory.
        Mandatorily requires a valid external validation reference.
        """
        # 1. Enforce validation reference presence
        if not external_validation_ref:
            return False, "Blocked: Promotion requires a valid independent external validation reference."

        # 2. Enforce formatting/rule for the external validation reference (must be a valid V86 reference)
        ref_str = str(external_validation_ref).lower()
        if not (ref_str.startswith("v86_val_") or ref_str.startswith("validation_v86_")):
            return False, f"Blocked: Validation reference '{external_validation_ref}' is not an approved V86 validation record."

        # 3. High confidence check
        if candidate.confidence_score < 0.70:
            return False, f"Blocked: Candidate confidence score {candidate.confidence_score} is below threshold 0.70."

        return True, "Approved"
