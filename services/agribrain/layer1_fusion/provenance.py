"""
Layer 1: Provenance & Lineage Engine (Spec v2)
Tracks the "Recipe" of every Fusion Run to ensure reproducibility and auditability.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

# --- 1. Deterministic ID Generation ---

def generate_evidence_id(source_type: str, timestamp: str, geometry_wkt: str, payload_hash: str) -> str:
    """
    evidence_id = hash(source + timestamp + geometry + payload)
    Guarantees that re-ingesting the same S2 scene yields the same ID.
    """
    raw = f"{source_type}|{timestamp}|{geometry_wkt}|{payload_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def generate_run_id(plot_id: str, start_date: str, end_date: str, params_hash: str, code_version: str) -> str:
    """
    run_id = hash(plot_id + time_range + config + code_version)
    Two identical runs will have the same ID (idempotency).
    """
    raw = f"{plot_id}|{start_date}|{end_date}|{params_hash}|{code_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

# --- 2. Data Structures (DAG Nodes) ---

@dataclass
class LineageEvent:
    """
    Append-only log of a pipeline step.
    e.g. "VALIDATED_EVIDENCE" or "GENERATED_TENSOR"
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "GENERIC"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    input_ids: List[str] = field(default_factory=list) # Upstream artifacts
    output_ids: List[str] = field(default_factory=list) # Downstream artifacts
    metadata: Dict[str, Any] = field(default_factory=dict) # Params used (e.g. "cloud_threshold": 30)

@dataclass
class FusionRun:
    """
    The Root Node of the Provenance Graph.
    Represents one execution of the Data Fusion Engine.
    """
    run_id: str
    plot_id: str
    start_date: str
    end_date: str
    
    # Context
    code_version: str
    params_hash: str
    backend: str
    
    # Status
    status: str = "PENDING" # PENDING, COMPLETED, FAILED
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_ms: float = 0.0
    
    # The DAG log
    events: List[LineageEvent] = field(default_factory=list)
    
    # Final Inventory
    input_evidence_count: int = 0
    rejected_evidence_count: int = 0
    
    def to_dict(self):
        return asdict(self)

# --- 3. The Tracker (Integration Hook) ---

class ProvenanceTracker:
    """
    Sits inside DataFusionEngine.
    Records every step of the pipeline.
    """
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: List[LineageEvent] = []
        
    def log_event(self, 
                  event_type: str, 
                  inputs: List[str] = None, 
                  outputs: List[str] = None, 
                  metadata: Dict[str, Any] = None):
        """
        Records a pipeline event.
        """
        event = LineageEvent(
            event_type=event_type,
            input_ids=inputs or [],
            output_ids=outputs or [],
            metadata=metadata or {}
        )
        self.events.append(event)
        # In a real system, we'd emit this to a DB or Kafka here
        # print(f"📜 [Prov] {event_type} (Ins={len(event.input_ids)}, Outs={len(event.output_ids)})")

    def export_lineage(self) -> List[Dict]:
        return [asdict(e) for e in self.events]
