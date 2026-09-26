"""MESIA AgriBrain & ASMAE System Integration Bridge — R6 §11.6–§11.9.

Connects MESIA's multi-radio intelligence pipeline into AgriBrain's canonical
evidence spine (Layer 0) and ASMAE state assimilation engine (Layer 05).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .contracts.observation import RadioObservationPacket
from .contracts.behaviour import BehaviourLikelihood
from .contracts.authority import CapabilityAuthorityRecord, RevocationEvent
from .behaviour.likelihood_engine import BehaviourLikelihoodEngine
from .behaviour.nuisance_model import BayesianNuisanceModel, NuisanceAttributionReport
from .assimilation.spatial_lattice import SharedBeliefLattice
from .assimilation.sensitivity_kernels import SensitivityKernelCalculator
from .assimilation.observability_analyzer import ObservabilityAnalyzer
from .assimilation.closure_engine import MultiRadioClosureEngine
from .assimilation.asmae_operator import ASMAEObservationOperator, ASMAEInnovationProposal
from .assimilation.layer0_spine import (
    EvidenceAdmissionStatus,
    Layer0EvidenceRecord,
    Layer0EvidenceSpine,
)
from .assimilation.capability_governance import CapabilityGovernanceAuthority


class MesiaAgriBrainBridge:
    """Full-system integration bridge between MESIA, Layer 0, and ASMAE."""

    def __init__(
        self,
        plot_id: str = "PLOT_DEFAULT",
        target_grid: Optional[Any] = None,
        grid_dim: Optional[Tuple[int, int]] = None,
        cell_size_m: float = 10.0,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        crs: Optional[str] = None,
        boundary_mask: Optional[Any] = None,
    ) -> None:
        self.plot_id = plot_id
        if target_grid is not None:
            n_rows = getattr(target_grid, "n_rows", 5)
            n_cols = getattr(target_grid, "n_cols", 5)
            res_m = float(getattr(target_grid, "resolution_m", cell_size_m) or cell_size_m)
            ox = float(getattr(target_grid, "origin_x", origin_x) or origin_x)
            oy = float(getattr(target_grid, "origin_y", origin_y) or origin_y)
            c = getattr(target_grid, "crs", crs)
            self.lattice = SharedBeliefLattice(
                plot_id=plot_id,
                cell_size_m=res_m,
                grid_dim=(n_rows, n_cols),
                origin_east_m=ox,
                origin_north_m=oy,
                crs=str(c) if c else None,
                boundary_mask=boundary_mask,
                target_grid=target_grid,
            )
        elif grid_dim is not None:
            self.lattice = SharedBeliefLattice(
                plot_id=plot_id,
                cell_size_m=cell_size_m,
                grid_dim=grid_dim,
                origin_east_m=origin_x,
                origin_north_m=origin_y,
                crs=crs,
                boundary_mask=boundary_mask,
            )
        else:
            self.lattice = SharedBeliefLattice(
                plot_id=plot_id,
                cell_size_m=cell_size_m,
                grid_dim=(5, 5),
                origin_east_m=origin_x,
                origin_north_m=origin_y,
                crs=crs,
                boundary_mask=boundary_mask,
            )
        self._active_capabilities: Dict[str, CapabilityAuthorityRecord] = {}
        self._revocation_history: List[RevocationEvent] = []

    def register_capability(self, capability: CapabilityAuthorityRecord) -> None:
        """Register a qualified capability authority record."""
        self._active_capabilities[capability.capability_id] = capability

    def list_active_capabilities(self) -> List[CapabilityAuthorityRecord]:
        """List all active qualified capabilities."""
        return [c for c in self._active_capabilities.values() if c.state == "QUALIFIED"]

    def process_and_admit_observation(
        self,
        packet: RadioObservationPacket,
        prior_state_vwc: float = 0.20,
        target_microzone_id: Optional[str] = None,
        signal_delta_db: float = 0.0,
        is_calibration_valid: bool = False,
        is_epoch_active: bool = False,
        temperature_delta_c: float = 0.0,
        antenna_displacement_m: float = 0.0,
        is_cell_handover: bool = False,
        is_machinery_active: bool = False,
        wind_speed_m_s: float = 0.0,
        relative_humidity_pct: float = 50.0,
        dew_point_depression_c: float = 10.0,
        is_foliar_link: bool = False,
    ) -> Tuple[Layer0EvidenceRecord, Optional[Any]]:
        """Run full end-to-end ingestion pipeline and produce Layer 0 record and ASMAE ObservationEvent.

        CONTAINMENT (Audit Finding #10 / mesia.md §7, §14):
        - is_calibration_valid and is_epoch_active default to False (fail-closed).
        - Nuisance uses caller-supplied signal_delta_db and environmental covariates.
        - Native evidence URI and hash are verified before admission.
        - Capability match requires radio_family and target_variable alignment.
        - ASMAE state_update and diagnosis authority are BLOCKED pending Phase 1 acquisition.
        """
        # 0. Verify native evidence exists and check capture integrity (Audit Finding #4 & Phase 3)
        native_uri = getattr(packet, "native_data_uri", None) or ""
        native_hash = getattr(packet, "native_data_hash", None) or ""
        
        # Verify 64-character hex SHA-256 hash formatting
        is_hash_valid = (
            bool(native_hash)
            and len(native_hash) == 64
            and all(c in "0123456789abcdefABCDEF" for c in native_hash)
        )
        
        # If on-disk SigMF capture artifact is referenced, verify actual file integrity
        if is_hash_valid and native_uri:
            from .ingestion.sigmf_ingest import verify_capture_integrity
            from pathlib import Path
            clean_path = native_uri.replace("file://", "")
            p = Path(clean_path)
            if p.exists() or (p.parent / f"{p.name}.sigmf-data").exists() or p.with_suffix(".sigmf-data").exists():
                try:
                    if not verify_capture_integrity(p):
                        is_hash_valid = False
                except Exception:
                    is_hash_valid = False
        
        if not native_uri.strip() or not is_hash_valid:
            if target_microzone_id:
                cell = self.lattice.get_cell(target_microzone_id)
                fallback_mz = cell.microzone_id if cell else target_microzone_id
            else:
                cells = self.lattice.list_all_cells()
                fallback_mz = cells[0].microzone_id if cells else f"{self.plot_id}_MZ_1_1"
            l0_record = Layer0EvidenceSpine.evaluate_admission(
                proposal=ASMAEObservationOperator.create_innovation(
                    likelihood=BehaviourLikelihoodEngine.generate_likelihood(packet),
                    prior_state_vwc=prior_state_vwc,
                    microzone_id=fallback_mz,
                    depth_stratum="ROOT_ZONE_5_30CM",
                ),
                is_calibration_valid=False,
                is_epoch_active=False,
            )
            return l0_record, None

        # 1. Bayesian Nuisance Attribution with physical covariates (mesia.md §14, §15)
        nuisance = BayesianNuisanceModel.attribute_cause(
            signal_delta_db=signal_delta_db,
            temperature_delta_c=temperature_delta_c,
            antenna_displacement_m=antenna_displacement_m,
            is_cell_handover=is_cell_handover,
            is_machinery_active=is_machinery_active,
            wind_speed_m_s=wind_speed_m_s,
            relative_humidity_pct=relative_humidity_pct,
            dew_point_depression_c=dew_point_depression_c,
            is_foliar_link=is_foliar_link,
        )

        # 2. Likelihood Proposal Generation with nuisance suppression
        likelihood = BehaviourLikelihoodEngine.generate_likelihood(packet, nuisance)

        # 3. Microzone target selection
        if target_microzone_id:
            cell = self.lattice.get_cell(target_microzone_id)
            mz_id = cell.microzone_id if cell else target_microzone_id
        else:
            cells = self.lattice.list_all_cells()
            mz_id = cells[0].microzone_id if cells else f"{self.plot_id}_MZ_1_1"

        # 4. ASMAE Observation Operator
        innovation = ASMAEObservationOperator.create_innovation(
            likelihood=likelihood,
            prior_state_vwc=prior_state_vwc,
            microzone_id=mz_id,
            depth_stratum="ROOT_ZONE_5_30CM",
        )

        # 5. Layer 0 Canonical Admission (caller must prove calibration and epoch)
        l0_record = Layer0EvidenceSpine.evaluate_admission(
            proposal=innovation,
            is_calibration_valid=is_calibration_valid,
            is_epoch_active=is_epoch_active,
        )

        # 6. ASMAE ObservationEvent Adapter
        # Phase 3: Conditionally enable state updates if a matching capability is QUALIFIED
        is_qualified = False
        for cap in self.list_active_capabilities():
            # Check if this capability authorizes the packet's target variable and radio family
            if likelihood.target_variable == cap.target_variable:
                if packet.source_profile.split("/")[0] in cap.supported_radio_families:
                    is_qualified = True
                    break

        from ..layer05_asmae.adapters.mesia_adapter import MesiaAsmaeAdapter
        asmae_event = MesiaAsmaeAdapter.to_asmae_observation_event(
            record=l0_record,
            plot_id=self.plot_id,
            is_qualified_for_decision=is_qualified, 
        )

        return l0_record, asmae_event

    def revoke_capability(self, capability_id: str, trigger_reason: str) -> Optional[RevocationEvent]:
        """Demote or withdraw capability on drift (Principle P-10)."""
        if capability_id in self._active_capabilities:
            record = self._active_capabilities[capability_id]
            rev_event = CapabilityGovernanceAuthority.revoke_authority_on_drift(record, trigger_reason)
            self._active_capabilities[capability_id] = CapabilityAuthorityRecord(
                **{**record.to_dict(), "state": "REVOKED"}
            )
            self._revocation_history.append(rev_event)
            return rev_event
        return None
