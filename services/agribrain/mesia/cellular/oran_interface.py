"""MESIA O-RAN Interface & E2 KPM Connector — R6 §13.6 / P11.6.

Bridges Open RAN E2 nodes and Near-RT RAN Intelligent Controllers (RIC)
to collect Key Performance Measurement (KPM) indicators over agricultural zones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .operator_bundle import OperatorEvidenceBundle


@dataclass(frozen=True)
class OranE2NodeStatus:
    """Status of an O-RAN E2 node connector."""

    node_id: str
    ran_function_id: int
    is_connected: bool
    last_kpm_report_at: datetime
    active_cu_up_count: int
    active_du_count: int


class OranConnector:
    """Manages ingestion of O-RAN E2 telemetry."""

    @staticmethod
    def parse_e2_kpm_indication(
        bundle_id: str,
        operator_name: str,
        cell_id: int,
        raw_kpm_data: Dict[str, Any],
    ) -> OperatorEvidenceBundle:
        """Parse raw E2 KPM indication message into an OperatorEvidenceBundle."""
        now = datetime.now(timezone.utc)

        # O-RAN E2 KPM definitions typically nest these within Measurement Records.
        # We enforce strict extraction rather than falling back to simulated data.
        
        try:
            tac = int(raw_kpm_data["tac"])
            plmn_id = str(raw_kpm_data["plmn"])
            
            # KPM metrics
            prb_usage = float(raw_kpm_data["prb_usage"])
            tx_power = float(raw_kpm_data["tx_power_dbm"])
            beam_id = int(raw_kpm_data.get("beam_id", -1))
            scheduler = str(raw_kpm_data.get("scheduler", "UNKNOWN"))
            ue_count = int(raw_kpm_data["ue_count"])
            
            # Cryptographic consent hook must be provided in real operator feeds
            consent_hook = raw_kpm_data.get("consent_hook_signature")
            if not consent_hook:
                raise ValueError("Missing cryptographic consent signature for operator data.")
                
        except KeyError as e:
            raise ValueError(f"Missing mandatory KPM metric in O-RAN feed: {e}")
            
        return OperatorEvidenceBundle(
            bundle_id=bundle_id,
            operator_name=operator_name,
            cell_id=cell_id,
            tracking_area_code=tac,
            plmn_id=plmn_id,
            recorded_at=now,
            prb_utilization_pct=prb_usage,
            mean_tx_power_dbm=tx_power,
            active_beam_index=beam_id,
            scheduler_mode=scheduler,
            anonymized_ue_count=ue_count,
            is_consent_valid=True,
            revocation_hook_ref=consent_hook,
        )
