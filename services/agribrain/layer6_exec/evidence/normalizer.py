
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List

from services.agribrain.layer6_exec.schema import (
    EvidenceType, NormalizedEvidence
)

def _generate_evidence_id(
    etype: EvidenceType,
    ts: str,
    plot_id: str,
    payload: Dict[str, Any]
) -> str:
    # Stable hash of content
    raw = f"{etype.value}|{ts}|{plot_id}|{json.dumps(payload, sort_keys=True, default=str)}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"EV-{h}"

def normalize_evidence_batch(
    raw_batch: List[Dict[str, Any]],
    plot_id: str
) -> List[NormalizedEvidence]:
    """
    Normalize raw evidence inputs into strict immutable records.
    """
    out: List[NormalizedEvidence] = []
    
    for item in raw_batch:
        try:
            # 1. Basic Validation
            raw_type = item.get("type", "").upper()
            try:
                etype = EvidenceType(raw_type)
            except ValueError:
                print(f"Skipping unknown evidence type: {raw_type}")
                continue
                
            ts = item.get("timestamp") or datetime.utcnow().isoformat()
            payload = item.get("payload", {})
            refs = item.get("source_refs", {})
            
            # 2. Type-Specific Validation (Lightweight)
            if etype == EvidenceType.SCOUT_FORM:
                if "severity" not in payload and "observed" not in payload:
                    continue # Invalid form
            
            # 3. Hash & Create
            ev_id = _generate_evidence_id(etype, ts, plot_id, payload)
            
            out.append(NormalizedEvidence(
                evidence_id=ev_id,
                type=etype,
                timestamp=ts,
                plot_id=plot_id,
                payload=payload,
                source_refs=refs,
                attachment_hashes=item.get("attachments", [])
            ))
            
        except Exception as e:
            print(f"Failed to normalize evidence item: {e}")
            
    return out
