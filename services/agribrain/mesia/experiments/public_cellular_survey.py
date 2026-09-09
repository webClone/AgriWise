"""MESIA E5 Public-Network Cellular Survey Harness — R6 §10.6 / P8.6.

Executes multi-operator cellular surveys (Mobilis, Djezzy, Ooredoo)
and evaluates tower stability, handovers, and passive channel quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OperatorSurveySummary:
    """Summary of a survey run across public cellular networks."""

    survey_id: str
    operator_name: str
    mcc_mnc: str
    primary_serving_cell_id: int
    mean_rsrp_dbm: float
    mean_rsrq_db: float
    handover_count: int
    is_stable_for_context: bool


class PublicCellularSurveyHarness:
    """Manages E5 multi-operator public network survey trials."""

    @staticmethod
    def run_operator_survey(
        survey_id: str,
        operator: str,
        cell_id: int,
        rsrp_samples: List[float],
        rsrq_samples: List[float],
        handovers: int = 0,
    ) -> OperatorSurveySummary:
        """Evaluate network stability for a specific cellular operator from survey samples."""
        if not rsrp_samples:
            raise ValueError("Cannot evaluate operator survey without RSRP samples.")
        if not rsrq_samples:
            raise ValueError("Cannot evaluate operator survey without RSRQ samples.")

        mean_rsrp = sum(rsrp_samples) / len(rsrp_samples)
        mean_rsrq = sum(rsrq_samples) / len(rsrq_samples)

        # Operator MCC/MNC lookup for Algerian networks
        operator_mcc_mnc = {
            "mobilis": "603-01",
            "djezzy": "603-02",
            "ooredoo": "603-03",
        }.get(operator.lower(), "603-99")

        # Stable for opportunistic passive sensing if coverage is adequate and handovers are rare
        is_stable = (mean_rsrp >= -115.0) and (mean_rsrq >= -18.0) and (handovers <= 2)

        return OperatorSurveySummary(
            survey_id=survey_id,
            operator_name=operator,
            mcc_mnc=operator_mcc_mnc,
            primary_serving_cell_id=cell_id,
            mean_rsrp_dbm=round(mean_rsrp, 2),
            mean_rsrq_db=round(mean_rsrq, 2),
            handover_count=handovers,
            is_stable_for_context=is_stable,
        )
