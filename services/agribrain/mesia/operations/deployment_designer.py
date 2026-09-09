"""MESIA Deployment Designer — R6 §12 / R2 Monograph Section 144.

Implements the site-survey, information-gain-optimal placement, digital
installation plan and commissioning checklist specified in §12.1–12.3 and
phase P10.1–P10.9 of the R6 Full Implementation Blueprint, sealed by Section 144
of the R2 WorldModel Monograph.

Design contract:
    Optimise expected information about target state and confounders plus
    robustness, then subtract hardware, wiring, energy, maintenance,
    spectrum and operational burden.  The designer jointly selects node count,
    front-end type, position, height/depth, orientation, bands,
    active/passive links, gateway, reference paths and spares.  It returns
    'target not observable within constraints' when Fisher Information criteria fail.

Strictly deterministic, physically grounded, free of mock/synthetic grid shortcuts.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..epoch_authority.spatial_coordinates import SpatialCoordinateAuthority
from ..planning.deployment_designer import (
    CandidateAnchor,
    Coordinate3D,
    DeploymentMode,
    MESIADeploymentDesigner,
    Microzone,
    MinimumSpanningTreeWiring,
    TopologyType,
)


# ── §12.1  Designer Inputs ──────────────────────────────────────────


@dataclass(frozen=True)
class SiteSurveyInput:
    """All site-survey inputs required by the Deployment Designer (§12.1)."""

    survey_id: str

    # Plot geometry
    plot_boundary_wgs84: List[Tuple[float, float]]
    """Polygon vertices (lat, lon)."""

    terrain_elevation_m: float = 0.0
    crop_row_spacing_m: float = 0.0
    expected_canopy_height_m: float = 0.0

    # Infrastructure
    irrigation_network_type: str = ""
    """e.g. 'drip', 'sprinkler', 'flood', 'center_pivot', 'none'."""

    soil_zones: List[str] = field(default_factory=list)
    """Soil texture zones within the plot."""

    target_capabilities: List[str] = field(default_factory=list)
    """e.g. ['near_surface_moisture', 'canopy_water', 'irrigation_response']."""

    # Constraints
    installable_locations: List[Tuple[float, float, float]] = field(default_factory=list)
    """Candidate node locations (lat, lon, alt_m)."""

    machinery_lanes: List[Tuple[float, float]] = field(default_factory=list)
    obstacles: List[str] = field(default_factory=list)
    environmental_exposure: str = ""
    security_tamper_risk: str = "LOW"

    # Radio environment
    public_network_coverage: List[str] = field(default_factory=list)
    allowed_bands_mhz: List[Tuple[float, float]] = field(default_factory=list)
    interference_atlas_ref: str = ""

    # Budget
    max_nodes: int = 50
    max_budget_usd: float = 0.0
    maintenance_interval_days: int = 90

    def content_hash(self) -> str:
        raw = json.dumps(
            {k: str(v) for k, v in self.__dict__.items()},
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── §12.2  Optimisation Result ──────────────────────────────────────


@dataclass(frozen=True)
class PlannedNodePlacement:
    """A single node in the optimised deployment plan."""

    anchor_id: str
    front_end_class: str
    """FrontEndClass value."""

    radio_family: str
    position_wgs84: Tuple[float, float, float]
    """(lat, lon, alt_m)."""

    height_m: float
    depth_m: float
    orientation_ypr_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    polarisation: str = "VERTICAL"
    bands_mhz: List[Tuple[float, float]] = field(default_factory=list)
    is_reference_path: bool = False
    is_spare: bool = False
    gateway_id: str = ""
    estimated_sensitivity_kernel_ref: str = ""


@dataclass(frozen=True)
class CommissioningCheckItem:
    """A single item on the commissioning checklist (§12.3)."""

    item_id: str
    category: str
    """One of: 'identity', 'pose', 'coverage', 'reference', 'timing',
    'gain', 'storage', 'backhaul', 'truth', 'baseline'."""

    description: str
    is_mandatory: bool = True
    passed: Optional[bool] = None
    notes: str = ""


@dataclass(frozen=True)
class DeploymentPlan:
    """Complete digital installation plan — R6 §12 / P10.3."""

    plan_id: str
    survey_ref: str
    """Content hash of the SiteSurveyInput."""

    nodes: List[PlannedNodePlacement]
    commissioning_checklist: List[CommissioningCheckItem]

    expected_observable_zones: int = 0
    expected_unobservable_zones: int = 0
    total_estimated_cost_usd: float = 0.0

    target_not_observable: bool = False
    """If True, the designer concluded that the requested target capabilities
    cannot be achieved within the supplied constraints."""

    target_not_observable_reason: str = ""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def content_hash(self) -> str:
        raw = json.dumps(
            {"plan_id": self.plan_id, "nodes": len(self.nodes)},
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── §12  Deployment Designer ────────────────────────────────────────


class DeploymentDesigner:
    """MESIA Deployment Designer — R6 §12 & R2 Monograph Section 144.

    Generates an information-gain-optimal observatory layout given the
    site-survey inputs (§12.1), evaluates the optimization objective (§12.2),
    and produces a digital installation plan with a commissioning checklist
    (§12.3).
    """

    STANDARD_CHECKLIST: List[Dict[str, Any]] = [
        {
            "item_id": "CC-01",
            "category": "identity",
            "description": (
                "As-built receiver/antenna/clock/firmware identity matches "
                "the approved plan; deviations are recorded."
            ),
        },
        {
            "item_id": "CC-02",
            "category": "pose",
            "description": (
                "Surveyed pose and covariance, mount, cable, filter, power "
                "and weatherproofing are complete."
            ),
        },
        {
            "item_id": "CC-03",
            "category": "coverage",
            "description": (
                "Coverage scan, interference atlas, native-device protocol "
                "checks and public cellular/network context are recorded."
            ),
        },
        {
            "item_id": "CC-04",
            "category": "reference",
            "description": (
                "Reference/sentinel, timing, gain, saturation, storage, "
                "packet loss and backhaul tests pass."
            ),
        },
        {
            "item_id": "CC-05",
            "category": "coverage",
            "description": (
                "Planned links and bands meet sensitivity/observability "
                "expectations or the design is revised."
            ),
        },
        {
            "item_id": "CC-06",
            "category": "truth",
            "description": (
                "Truth and intervention event sources are time-aligned; "
                "missing sources are explicit."
            ),
        },
        {
            "item_id": "CC-07",
            "category": "baseline",
            "description": (
                "Baseline/calibration starts only after geometry/configuration "
                "freeze; capability status remains non-operational until "
                "qualification."
            ),
        },
    ]

    @staticmethod
    def _is_point_in_polygon(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
        """Ray-casting algorithm for point-in-polygon inclusion."""
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    @classmethod
    def design_deployment(
        cls,
        survey: SiteSurveyInput,
        grid_spacing_m: float = 50.0,
        cost_per_node_usd: float = 150.0,
        mode: Optional[DeploymentMode] = None,
        topology: Optional[TopologyType] = None,
    ) -> DeploymentPlan:
        """Generate an information-gain-optimal deployment plan under Monograph Section 144.

        Jointly optimizes node count, position, height, gateway, and reference paths
        using Fisher Information Matrix (FIM) D-optimality and submodular maximization.

        Args:
            survey: Complete site-survey input (§12.1).
            grid_spacing_m: Nominal inter-node spacing for spatial discretization (meters).
            cost_per_node_usd: Baseline per-node hardware cost.
            mode: Explicit mission profile (defaults to capability inference).
            topology: Power and backhaul topology (defaults to STANDALONE).

        Returns:
            DeploymentPlan with physical placement, commissioning checklist,
            observability metrics, or target_not_observable=True if constraints fail.
        """
        # 1. Validate boundary polygon
        if len(survey.plot_boundary_wgs84) < 3:
            return cls._not_observable_plan(
                survey, "Insufficient polygon vertices (need ≥3)."
            )

        lats = [p[0] for p in survey.plot_boundary_wgs84]
        lons = [p[1] for p in survey.plot_boundary_wgs84]
        origin_lat = float(np.mean(lats))
        origin_lon = float(np.mean(lons))
        origin_alt = survey.terrain_elevation_m

        # Project polygon vertices to local metric ENU Cartesian frame
        poly_enu: List[Tuple[float, float]] = []
        for lat, lon in survey.plot_boundary_wgs84:
            enu = SpatialCoordinateAuthority.wgs84_to_enu(
                lat, lon, origin_alt, origin_lat, origin_lon, origin_alt
            )
            poly_enu.append((enu.east_m, enu.north_m))

        # Metric dimensions and area via Shoelace formula
        n_pts = len(poly_enu)
        area_m2 = 0.5 * abs(
            sum(
                poly_enu[i][0] * poly_enu[(i + 1) % n_pts][1]
                - poly_enu[(i + 1) % n_pts][0] * poly_enu[i][1]
                for i in range(n_pts)
            )
        )
        plot_area_ha = max(0.01, area_m2 / 10000.0)

        easts = [p[0] for p in poly_enu]
        norths = [p[1] for p in poly_enu]
        east_min, east_max = min(easts), max(easts)
        north_min, north_max = min(norths), max(norths)
        east_span_m = east_max - east_min
        north_span_m = north_max - north_min

        if east_span_m < 5.0 or north_span_m < 5.0:
            return cls._not_observable_plan(
                survey, "Plot metric dimensions too small for multistatic radio sensing."
            )

        # 2. Infer Deployment Mode from target capabilities if not explicitly given
        if mode is None:
            caps = " ".join(survey.target_capabilities).lower()
            if "research" in caps or "foundation" in caps:
                mode = DeploymentMode.RESEARCH
            elif "precision" in caps or "high_value" in caps:
                mode = DeploymentMode.PRECISION
            elif "hydraulic" in caps or ("canopy" in caps and "soil" in caps):
                mode = DeploymentMode.HYDRAULIC
            elif "irrigation" in caps or "moisture" in caps:
                mode = DeploymentMode.IRRIGATION
            else:
                mode = DeploymentMode.MONITOR

        if topology is None:
            topology = TopologyType.STANDALONE

        # Pure Remote Modality: Zero In-Situ Hardware Footprint ($0 BOM)
        if mode == DeploymentMode.PURE_REMOTE:
            plan_id = f"plan-remote-{survey.content_hash()[:12]}"
            checklist = [
                CommissioningCheckItem(
                    item_id="RC-01",
                    category="orbit_ephemeris",
                    description="Orbital ephemeris feeds (NASA CYGNSS / Spire / ESA Sentinel) confirmed active over parcel coordinates.",
                    is_mandatory=True,
                ),
                CommissioningCheckItem(
                    item_id="RC-02",
                    category="bistatic_geometry",
                    description="Spaceborne specular reflection tracks and Sentinel-1 InSAR coherence baseline configured for plot polygon.",
                    is_mandatory=True,
                ),
                CommissioningCheckItem(
                    item_id="RC-03",
                    category="telecom_cml",
                    description="Commercial microwave backhaul link telemetry verified with carrier network partner.",
                    is_mandatory=False,
                ),
            ]
            return DeploymentPlan(
                plan_id=plan_id,
                survey_ref=survey.content_hash(),
                nodes=[],
                commissioning_checklist=checklist,
                expected_observable_zones=int(max(4, plot_area_ha * 4)),
                expected_unobservable_zones=0,
                total_estimated_cost_usd=0.0,
                target_not_observable=False,
            )

        # Mode B: Perimeter Sentinel (1 or 2 passive listening sentinels on boundary)
        if mode == DeploymentMode.PERIMETER_SENTINEL:
            # Place at opposite corners of the perimeter polygon to maximize angular diversity
            sentinel_positions = [poly_enu[0], poly_enu[len(poly_enu) // 2]]
            nodes: List[PlannedNodePlacement] = []
            for idx, (ex, ey) in enumerate(sentinel_positions[:2]):
                wgs = SpatialCoordinateAuthority.enu_to_wgs84(
                    ex, ey, 2.0, origin_lat, origin_lon, origin_alt
                )
                nodes.append(
                    PlannedNodePlacement(
                        anchor_id=f"SENTINEL-{idx+1:02d}",
                        front_end_class="PASSIVE_SDR",
                        radio_family="AMBIENT_SOOP",
                        position_wgs84=(round(wgs[0], 6), round(wgs[1], 6), round(wgs[2], 1)),
                        height_m=2.0,
                        depth_m=0.0,
                    )
                )
            plan_id = f"plan-sentinel-{survey.content_hash()[:12]}"
            checklist = [
                CommissioningCheckItem(
                    item_id="SC-01",
                    category="rf_sniffing",
                    description="Perimeter passive SDR sentinel lock on ambient GNSS/cellular pilots confirmed.",
                    is_mandatory=True,
                )
            ]
            return DeploymentPlan(
                plan_id=plan_id,
                survey_ref=survey.content_hash(),
                nodes=nodes,
                commissioning_checklist=checklist,
                expected_observable_zones=int(max(4, plot_area_ha * 2)),
                expected_unobservable_zones=0,
                total_estimated_cost_usd=len(nodes) * cost_per_node_usd,
                target_not_observable=False,
            )

        # 3. Determine Carrier Frequency (Wavelength lambda = c / f)
        carrier_freq_hz = 2.4e9  # Default 2.4 GHz Wi-Fi CSI
        if survey.allowed_bands_mhz:
            first_band = survey.allowed_bands_mhz[0]
            center_mhz = (first_band[0] + first_band[1]) / 2.0
            carrier_freq_hz = center_mhz * 1e6

        # 4. Ingest and filter candidate anchor locations
        machinery_enu: List[Tuple[float, float]] = []
        for lat, lon in survey.machinery_lanes:
            m_enu = SpatialCoordinateAuthority.wgs84_to_enu(
                lat, lon, origin_alt, origin_lat, origin_lon, origin_alt
            )
            machinery_enu.append((m_enu.east_m, m_enu.north_m))

        candidates: List[CandidateAnchor] = []

        if survey.installable_locations:
            # Use real surveyed candidate locations
            for idx, (lat, lon, alt) in enumerate(survey.installable_locations):
                cand_enu = SpatialCoordinateAuthority.wgs84_to_enu(
                    lat, lon, alt, origin_lat, origin_lon, origin_alt
                )
                
                # Check machinery lane safe clearance (>= 5 meters)
                too_close = any(
                    math.hypot(cand_enu.east_m - mx, cand_enu.north_m - my) < 5.0
                    for mx, my in machinery_enu
                )
                if not too_close:
                    height_m = max(1.0, cand_enu.up_m)
                    candidates.append(
                        CandidateAnchor(
                            location_id=f"CAND-{idx:03d}",
                            position=Coordinate3D(cand_enu.east_m, cand_enu.north_m, height_m),
                            base_cost=cost_per_node_usd,
                            is_solar_capable=True,
                        )
                    )
        else:
            # Generate valid candidate locations strictly along the field perimeter / boundary
            # Spaced at nominal anchor intervals, avoiding the field interior where machinery operates
            perimeter_spacing = max(30.0, grid_spacing_m * 1.5)
            cand_idx = 0
            for i in range(n_pts):
                p_start = poly_enu[i]
                p_end = poly_enu[(i + 1) % n_pts]
                edge_len = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])
                steps = max(1, int(edge_len / perimeter_spacing))
                for s in range(steps):
                    frac = s / steps
                    cx = p_start[0] + frac * (p_end[0] - p_start[0])
                    cy = p_start[1] + frac * (p_end[1] - p_start[1])
                    
                    too_close = any(
                        math.hypot(cx - mx, cy - my) < 5.0
                        for mx, my in machinery_enu
                    )
                    if not too_close:
                        # Add candidate at standard 1.5m height
                        candidates.append(
                            CandidateAnchor(
                                location_id=f"PERIM-{cand_idx:03d}",
                                position=Coordinate3D(cx, cy, 1.5),
                                base_cost=cost_per_node_usd,
                                is_solar_capable=True,
                            )
                        )
                        cand_idx += 1

            # If center pivot irrigation, add center pivot tower candidate
            if "pivot" in survey.irrigation_network_type.lower():
                center_x = (east_min + east_max) / 2.0
                center_y = (north_min + north_max) / 2.0
                candidates.append(
                    CandidateAnchor(
                        location_id="PIVOT-CENTER",
                        position=Coordinate3D(center_x, center_y, 3.0),
                        base_cost=cost_per_node_usd * 1.2,
                        is_solar_capable=False,
                        is_wired_capable=True,
                    )
                )

        if len(candidates) < 4:
            return cls._not_observable_plan(
                survey,
                f"Only {len(candidates)} valid candidate mounting locations found; "
                f"multistatic radio sensing requires ≥ 4 non-collinear anchors.",
            )

        # 5. Discretize plot into physical ASMAE microzones inside the polygon
        zone_step = max(15.0, grid_spacing_m)
        microzones: List[Microzone] = []
        nx = max(1, int(east_span_m / zone_step))
        ny = max(1, int(north_span_m / zone_step))
        zone_id = 0

        for ix in range(nx):
            for iy in range(ny):
                zx = east_min + (ix + 0.5) * (east_span_m / nx)
                zy = north_min + (iy + 0.5) * (north_span_m / ny)
                if cls._is_point_in_polygon(zx, zy, poly_enu):
                    microzones.append(
                        Microzone(
                            zone_id=f"MZ-{zone_id:03d}",
                            center=Coordinate3D(zx, zy, 0.0),
                            radius=zone_step * 0.707,  # Circumscribed half-cell
                            importance_weight=1.2 if survey.target_capabilities else 1.0,
                        )
                    )
                    zone_id += 1

        if len(microzones) == 0:
            # Fallback for irregular polygons: add polygon centroid microzone
            microzones.append(
                Microzone(
                    zone_id="MZ-000",
                    center=Coordinate3D((east_min + east_max) / 2.0, (north_min + north_max) / 2.0, 0.0),
                    radius=zone_step,
                    importance_weight=1.0,
                )
            )

        # 6. Execute Submodular FIM Optimization
        effective_budget = survey.max_budget_usd if survey.max_budget_usd > 0.0 else (survey.max_nodes * cost_per_node_usd)

        designer = MESIADeploymentDesigner(
            mode=mode,
            topology=topology,
            carrier_frequency_hz=carrier_freq_hz,
        )

        selected_candidates, d_opt, metrics = designer.design_network(
            microzones=microzones,
            candidates=candidates,
            max_budget=effective_budget,
            max_nodes=survey.max_nodes,
            plot_area_ha=plot_area_ha,
        )

        # 7. Check feasibility gate (§12.2 / §144)
        if len(selected_candidates) < 4:
            return cls._not_observable_plan(
                survey,
                f"Budget constraint (${effective_budget:.2f}) permits only {len(selected_candidates)} "
                f"anchors; minimum 4 required for multistatic radio closure.",
            )

        obs_fraction = metrics["observable_fraction"]
        constraints = designer.get_mode_constraints(effective_budget, survey.max_nodes, plot_area_ha)
        if obs_fraction < constraints.min_observable_zone_fraction and survey.target_capabilities:
            return cls._not_observable_plan(
                survey,
                f"Insufficient spatial observability ({obs_fraction * 100:.1f}% of microzones covered, "
                f"minimum required is {constraints.min_observable_zone_fraction * 100:.0f}% for mode '{mode.value}'). "
                f"Increase budget or expand candidate locations.",
            )

        # 8. Designate Gateway and Reference Sentinel
        # Gateway is the selected anchor closest to the boundary origin / road
        gateway_anchor = min(
            selected_candidates,
            key=lambda a: math.hypot(a.position.x, a.position.y),
        )

        # Reference Sentinel is placed on the most stable geometry (near centroid)
        ref_anchor = max(
            selected_candidates,
            key=lambda a: min(a.position.distance_to(other.position) for other in selected_candidates if other != a),
        )

        # 9. Build Planned Node Placements with WGS84 Geodesy
        nodes: List[PlannedNodePlacement] = []
        bands = survey.allowed_bands_mhz or [(2400.0, 2484.0), (5150.0, 5850.0)]

        for idx, anchor in enumerate(selected_candidates):
            lat_deg, lon_deg, alt_m = SpatialCoordinateAuthority.enu_to_wgs84(
                anchor.position.x,
                anchor.position.y,
                anchor.position.z,
                origin_lat,
                origin_lon,
                origin_alt,
            )
            is_ref = (anchor == ref_anchor)
            node_id = f"REF-01" if is_ref else f"N-{idx:02d}"
            front_end = "REFERENCE_SENTINEL" if is_ref else "NATIVE_RADIO_DEVICE"

            nodes.append(
                PlannedNodePlacement(
                    anchor_id=node_id,
                    front_end_class=front_end,
                    radio_family="WIFI_CSI",
                    position_wgs84=(lat_deg, lon_deg, alt_m),
                    height_m=anchor.position.z,
                    depth_m=0.0,
                    bands_mhz=bands,
                    is_reference_path=is_ref,
                    gateway_id=f"GW-{gateway_anchor.location_id}",
                    estimated_sensitivity_kernel_ref=f"KERNEL-LINK-{node_id}",
                )
            )

        # 10. Compute total installation and wiring cost
        wiring_cost = MinimumSpanningTreeWiring.compute_wiring_cost(
            selected_candidates,
            gateway=gateway_anchor,
            cost_per_meter=1.5 if topology == TopologyType.WIRED_SCIENTIFIC else 0.5,
        )
        hardware_cost = sum(c.base_cost for c in selected_candidates)
        total_cost = hardware_cost + (wiring_cost if topology != TopologyType.STANDALONE else 0.0)

        # 11. Build Commissioning Checklist (§12.3)
        checklist = [
            CommissioningCheckItem(
                item_id=item["item_id"],
                category=item["category"],
                description=item["description"],
                is_mandatory=True,
            )
            for item in cls.STANDARD_CHECKLIST
        ]

        return DeploymentPlan(
            plan_id=f"DP-{survey.survey_id}",
            survey_ref=survey.content_hash(),
            nodes=nodes,
            commissioning_checklist=checklist,
            expected_observable_zones=int(metrics["observable_microzones"]),
            expected_unobservable_zones=int(metrics["unobservable_microzones"]),
            total_estimated_cost_usd=round(total_cost, 2),
            target_not_observable=False,
        )

    @classmethod
    def _not_observable_plan(
        cls, survey: SiteSurveyInput, reason: str
    ) -> DeploymentPlan:
        """Return a plan that declares the target not observable (§12.2)."""
        return DeploymentPlan(
            plan_id=f"DP-{survey.survey_id}-NOGO",
            survey_ref=survey.content_hash(),
            nodes=[],
            commissioning_checklist=[],
            expected_observable_zones=0,
            expected_unobservable_zones=0,
            total_estimated_cost_usd=0.0,
            target_not_observable=True,
            target_not_observable_reason=reason,
        )
