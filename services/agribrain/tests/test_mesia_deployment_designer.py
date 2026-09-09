"""Unit and regression tests for the unified, mathematically sealed MESIA Deployment Designer."""

import math
import numpy as np
import pytest

from services.agribrain.mesia.operations.deployment_designer import (
    SiteSurveyInput,
    PlannedNodePlacement,
    CommissioningCheckItem,
    DeploymentPlan,
    DeploymentDesigner,
)
from services.agribrain.mesia.planning.deployment_designer import (
    CandidateAnchor,
    Coordinate3D,
    DeploymentMode,
    FIMEvaluator,
    MESIADeploymentDesigner,
    Microzone,
    TopologyType,
)


def test_deployment_designer_physical_fresnel_and_fim() -> None:
    """Verifies that the FIM D-optimality engine computes physical Fresnel scattering without mocks."""
    # 5 microzones in a 200m field
    microzones = [
        Microzone("MZ-1", Coordinate3D(50.0, 50.0, 0.0), radius=25.0),
        Microzone("MZ-2", Coordinate3D(150.0, 50.0, 0.0), radius=25.0),
        Microzone("MZ-3", Coordinate3D(100.0, 100.0, 0.0), radius=30.0),
        Microzone("MZ-4", Coordinate3D(50.0, 150.0, 0.0), radius=25.0),
        Microzone("MZ-5", Coordinate3D(150.0, 150.0, 0.0), radius=25.0),
    ]

    evaluator_24ghz = FIMEvaluator(microzones=microzones, carrier_frequency_hz=2.4e9)
    evaluator_868mhz = FIMEvaluator(microzones=microzones, carrier_frequency_hz=868e6)

    # 868 MHz has longer wavelength than 2.4 GHz
    assert evaluator_868mhz.wavelength > evaluator_24ghz.wavelength
    assert math.isclose(evaluator_24ghz.wavelength, 0.125, rel_tol=0.01)
    assert math.isclose(evaluator_868mhz.wavelength, 0.345, rel_tol=0.01)

    a1 = CandidateAnchor("A1", Coordinate3D(0.0, 100.0, 1.5))
    a2 = CandidateAnchor("A2", Coordinate3D(200.0, 100.0, 1.5))

    phi_24 = evaluator_24ghz.compute_link_sensitivity(a1, a2)
    phi_868 = evaluator_868mhz.compute_link_sensitivity(a1, a2)

    # Central microzone (MZ-3 at 100, 100) lies directly on the line of sight
    assert phi_24[2] > 0.5
    assert phi_868[2] > 0.5

    # Microzones off the line of sight (MZ-1 at 50, 50, perp dist ~ 50m) have lower sensitivity
    assert phi_24[0] < phi_24[2]
    assert phi_868[0] < phi_868[2]

    # Two nodes produce 1 link -> FIM is valid
    fim = evaluator_24ghz.compute_fim([a1, a2])
    assert fim.shape == (5, 5)
    d_opt = evaluator_24ghz.d_optimality([a1, a2])
    assert np.isfinite(d_opt)


def test_deployment_designer_commercial_50ha_no_mocks() -> None:
    """Verifies that DeploymentDesigner optimizes a 50ha commercial plot without mock data."""
    center_lat, center_lon, alt_m = 33.3675, 6.8520, 80.0
    d_lat, d_lon = 0.0063, 0.0077

    boundary = [
        (center_lat - d_lat / 2, center_lon - d_lon / 2),
        (center_lat - d_lat / 2, center_lon + d_lon / 2),
        (center_lat + d_lat / 2, center_lon + d_lon / 2),
        (center_lat + d_lat / 2, center_lon - d_lon / 2),
    ]

    machinery_lane = [
        (center_lat - d_lat / 2, center_lon),
        (center_lat, center_lon),
        (center_lat + d_lat / 2, center_lon),
    ]

    # Sample candidate locations along all 4 boundary fences and center pivot
    candidates = []
    for lat in np.linspace(center_lat - d_lat / 2, center_lat + d_lat / 2, 4):
        candidates.append((lat, center_lon - d_lon / 2, alt_m + 1.5))
        candidates.append((lat, center_lon + d_lon / 2, alt_m + 1.5))
    for lon in np.linspace(center_lon - d_lon / 2, center_lon + d_lon / 2, 4):
        candidates.append((center_lat - d_lat / 2, lon, alt_m + 1.5))
        candidates.append((center_lat + d_lat / 2, lon, alt_m + 1.5))

    # Center pivot irrigation tower
    candidates.append((center_lat, center_lon + 0.0010, alt_m + 3.0))

    # Add candidate directly in the machinery lane (should be excluded)
    candidates.append((center_lat, center_lon, alt_m + 1.5))

    survey = SiteSurveyInput(
        survey_id="SURVEY_50HA_TEST",
        plot_boundary_wgs84=boundary,
        terrain_elevation_m=alt_m,
        installable_locations=candidates,
        machinery_lanes=machinery_lane,
        target_capabilities=["near_surface_moisture"],
        max_budget_usd=3000.0,
        max_nodes=12,
    )

    plan = DeploymentDesigner.design_deployment(
        survey=survey,
        grid_spacing_m=75.0,
        cost_per_node_usd=200.0,
        mode=DeploymentMode.IRRIGATION,
    )

    assert not plan.target_not_observable
    assert len(plan.nodes) >= 4
    assert plan.total_estimated_cost_usd <= survey.max_budget_usd
    assert plan.expected_observable_zones > 0

    # Safety check: no selected node inside machinery lane buffer
    for node in plan.nodes:
        min_dist = min(
            math.hypot(node.position_wgs84[0] - ml[0], node.position_wgs84[1] - ml[1]) * 111320.0
            for ml in machinery_lane
        )
        assert min_dist >= 4.9

    # Reference sentinel check
    ref_nodes = [n for n in plan.nodes if n.is_reference_path]
    assert len(ref_nodes) == 1
    assert ref_nodes[0].front_end_class == "REFERENCE_SENTINEL"

    # Commissioning checklist check
    assert len(plan.commissioning_checklist) == 7


def test_deployment_designer_feasibility_gate() -> None:
    """Verifies that the feasibility gate declares target_not_observable=True when budget fails."""
    boundary = [
        (33.36, 6.85),
        (33.36, 6.86),
        (33.37, 6.86),
        (33.37, 6.85),
    ]

    survey_impossible = SiteSurveyInput(
        survey_id="UNDERFUNDED_TEST",
        plot_boundary_wgs84=boundary,
        max_budget_usd=100.0,  # Impossible: cannot afford 4 nodes at $200
        target_capabilities=["near_surface_moisture"],
    )

    plan = DeploymentDesigner.design_deployment(survey=survey_impossible, cost_per_node_usd=200.0)
    assert plan.target_not_observable
    assert "budget" in plan.target_not_observable_reason.lower() or "insufficient" in plan.target_not_observable_reason.lower()
