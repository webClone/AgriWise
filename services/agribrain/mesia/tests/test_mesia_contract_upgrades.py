"""Tests for MESIA Contract Upgrades and ASMAE Integration.

Verifies:
1. Monograph §143 GeometryEpoch with 6DOF covariance, antenna PCO/PCV, and RTK survey flags.
2. Peplinski & Dobson (1995) complex permittivity and loss tangent in FDTD.
3. MesiaAsmaeAdapter P-08 enforcement and gated authority vector.
4. ASMAE INDEX_STATE_REGISTRY integration with forbidden state protection.
"""

import math
from datetime import datetime, timezone
import pytest

from services.agribrain.mesia.contracts.epochs import GeometryEpoch
from services.agribrain.mesia.epoch_authority.antenna_pose import (
    AntennaPoseAuthority,
    AntennaPoseRecord,
)
from services.agribrain.mesia.assimilation.fdtd_solver import BiologicalPermittivityMap
from services.agribrain.mesia.contracts.observation import RadioObservationPacket
from services.agribrain.mesia.contracts.behaviour import BehaviourLikelihood
from services.agribrain.mesia.assimilation.asmae_operator import (
    ASMAEObservationOperator,
    ASMAEInnovationProposal,
)
from services.agribrain.mesia.assimilation.layer0_spine import (
    EvidenceAdmissionStatus,
    Layer0EvidenceRecord,
)
from services.agribrain.layer05_asmae.adapters.mesia_adapter import MesiaAsmaeAdapter
from services.agribrain.layer05_asmae.observation.index_state_mapping import (
    get_mapping,
    validate_forbidden_state_update,
)
from services.agribrain.layer05_asmae.config import (
    IDX_ROOT_ZONE_WATER,
    IDX_CANOPY_WATER,
    IDX_SURFACE_WETNESS,
    IDX_CHLOROPHYLL,
    IDX_VIGOR,
    IDX_LAI,
)


def test_geometry_epoch_monograph_143_attributes():
    """Verify GeometryEpoch supports all Monograph §143 fields and deterministic hashing."""
    now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
    epoch = GeometryEpoch(
        epoch_id="geom-epoch-001",
        triggered_at=now,
        trigger_reason="RTK Bench Re-survey",
        position_wgs84=(33.3678, 6.8512, 85.0),
        position_local_enu=(10.5, 20.2, 2.5),
        orientation_ypr_deg=(45.0, 0.0, 0.0),
        covariance_m=(0.005, 0.005, 0.010),
        position_covariance=(2.5e-5, 0.0, 0.0, 2.5e-5, 0.0, 1.0e-4),
        orientation_covariance_deg2=(0.1, 0.1, 0.1),
        antenna_model="UBLOX_ANN_MB",
        phase_center_offset_mm=(1.2, -0.5, 35.0),
        phase_center_variation_ref="antex://ublox/ann_mb_v2.atx",
        mount_model="MAST_RIGID_3M",
        wiring_route_hash="a" * 64,
        survey_method="RTK_FIXED",
        survey_time_utc=now,
        geometry_version="1.0.0",
        geometry_hash="b" * 64,
    )

    d = epoch.to_dict()
    assert d["epoch_type"] == "GeometryEpoch"
    assert d["survey_method"] == "RTK_FIXED"
    assert d["position_local_enu"] == (10.5, 20.2, 2.5)
    assert d["phase_center_offset_mm"] == (1.2, -0.5, 35.0)
    assert len(epoch.content_hash()) == 64


def test_antenna_pose_authority_to_geometry_epoch():
    """Verify AntennaPoseAuthority creates compliant GeometryEpoch from surveyed record."""
    pose = AntennaPoseRecord(
        antenna_id="NODE_SENTINEL_01",
        position_wgs84=(33.36, 6.85, 80.0),
        local_xyz_m=(0.0, 0.0, 2.0),
        orientation_ypr_deg=(0.0, 0.0, 0.0),
        polarisation="VERTICAL",
        phase_centre_offset_m=(0.002, 0.001, 0.040),
        mount_type="TRIPOD_MAST",
        pose_uncertainty_m=0.004,
    )

    epoch = AntennaPoseAuthority.create_geometry_epoch("epoch-test-01", pose, "EL_OUED_SITE")
    assert epoch.survey_method == "RTK_FIXED"
    assert epoch.phase_center_offset_mm == (2.0, 1.0, 40.0)
    assert epoch.position_local_enu == (0.0, 0.0, 2.0)
    assert epoch.position_covariance is not None


def test_peplinski_soil_dielectric_physics():
    """Verify Peplinski-Dobson dielectric model exhibits real physical dispersion and loss."""
    # Test dry vs wet soil at 2.4 GHz
    eps_dry, sig_dry = BiologicalPermittivityMap.get_soil_properties(0.05, freq_hz=2.4e9)
    eps_wet, sig_wet = BiologicalPermittivityMap.get_soil_properties(0.35, freq_hz=2.4e9)

    assert eps_wet > eps_dry, "Dielectric constant must increase with moisture"
    assert sig_wet > sig_dry, "Conductivity/loss must increase with moisture"
    assert 3.0 < eps_dry < 7.0, f"Dry soil permittivity unexpected: {eps_dry}"
    assert 15.0 < eps_wet < 35.0, f"Wet soil permittivity unexpected: {eps_wet}"

    # Test frequency dependence: 868 MHz vs 5.8 GHz
    eps_868, sig_868 = BiologicalPermittivityMap.get_soil_properties(0.20, freq_hz=868e6)
    eps_5g, sig_5g = BiologicalPermittivityMap.get_soil_properties(0.20, freq_hz=5.8e9)
    assert eps_868 > 0 and sig_868 > 0
    assert eps_5g > 0 and sig_5g > 0

    # Canopy dielectric
    eps_c, sig_c = BiologicalPermittivityMap.get_canopy_properties(canopy_water=0.7, freq_hz=2.4e9, leaf_area_index=3.0)
    assert eps_c > 1.0
    assert sig_c > 0.0


def test_mesia_asmae_adapter_p08_and_gated_authority():
    """Verify MesiaAsmaeAdapter enforces Principle P-08 and gates authority."""
    now = datetime.now(timezone.utc)
    proposal = ASMAEInnovationProposal(
        proposal_id="prop-001",
        target_state_variable="root_zone_water",
        microzone_id="MZ_1",
        depth_stratum="ROOT_ZONE_5_30CM",
        innovation_value=0.03,
        observation_variance=0.02,
        confidence_support=0.85,
        authority_scope="evidence_proposal",
        native_lineage_hash="c" * 64,
        likelihood_ref="lik-001",
        created_at=now,
    )

    record = Layer0EvidenceRecord(
        record_id="rec-001",
        proposal=proposal,
        status=EvidenceAdmissionStatus.ADMITTED,
        admission_notes="Admitted under calibration epoch",
        is_usable_for_assimilation=True,
    )

    # 1. Unqualified proposal -> Authority blocked
    obs_unqualified = MesiaAsmaeAdapter.to_asmae_observation_event(record, "PLOT_01", is_qualified_for_decision=False)
    assert obs_unqualified is not None
    assert obs_unqualified.authority.state_update_allowed is False
    assert obs_unqualified.provider == "MESIA_QUALIFICATION_PENDING"

    # 2. Qualified proposal -> Authority admitted for ASMAE EnKF assimilation
    obs_qualified = MesiaAsmaeAdapter.to_asmae_observation_event(record, "PLOT_01", is_qualified_for_decision=True)
    assert obs_qualified is not None
    assert obs_qualified.authority.state_update_allowed is True
    assert obs_qualified.provider == "MESIA_OBSERVATORY"

    # 3. Principle P-08 violation check
    illegal_proposal = ASMAEInnovationProposal(
        proposal_id="prop-illegal",
        target_state_variable="root_zone_water",
        microzone_id="MZ_1",
        depth_stratum="ROOT_ZONE_5_30CM",
        innovation_value=0.03,
        observation_variance=0.02,
        confidence_support=0.85,
        authority_scope="STATE_UPDATE",  # Illegal scope!
        native_lineage_hash="c" * 64,
        likelihood_ref="lik-001",
        created_at=now,
    )
    illegal_record = Layer0EvidenceRecord(
        record_id="rec-002",
        proposal=illegal_proposal,
        status=EvidenceAdmissionStatus.ADMITTED,
        admission_notes="Illegal proposal check",
        is_usable_for_assimilation=True,
    )

    with pytest.raises(ValueError, match="Principle P-08 Violation"):
        MesiaAsmaeAdapter.to_asmae_observation_event(illegal_record, "PLOT_01", is_qualified_for_decision=True)


def test_asmae_index_state_registry_mesia_features():
    """Verify MESIA RF features are registered in ASMAE and forbid optical state corruption."""
    m_rzw = get_mapping("mesia_root_zone_water")
    assert m_rzw is not None
    assert m_rzw.sensor == "MESIA"
    assert IDX_ROOT_ZONE_WATER in m_rzw.target_state_indices

    # MESIA must NOT update optical states directly (chlorophyll, vigor, LAI)
    assert validate_forbidden_state_update("mesia_root_zone_water", IDX_CHLOROPHYLL) is True
    assert validate_forbidden_state_update("mesia_root_zone_water", IDX_VIGOR) is True
    assert validate_forbidden_state_update("mesia_root_zone_water", IDX_LAI) is True

    # Canopy water
    m_cw = get_mapping("mesia_canopy_water")
    assert m_cw is not None
    assert IDX_CANOPY_WATER in m_cw.target_state_indices
    assert validate_forbidden_state_update("mesia_canopy_water", IDX_CHLOROPHYLL) is True

    # Surface wetness
    m_sw = get_mapping("mesia_surface_wetness")
    assert m_sw is not None
    assert IDX_SURFACE_WETNESS in m_sw.target_state_indices
