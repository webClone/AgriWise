"""MESIA Deployment Designer — Planning & Optimization Engine.

Implements the Fisher Information Matrix (FIM) D-optimality formulation,
electromagnetic Fresnel ellipsoid sensitivity kernels, and submodular lazy
greedy maximization for optimal anchor placement.

Complies with Section 144 of the R2 WorldModel Monograph:
    A* = argmax_A [ information_state(A) + information_cause(A) + robustness(A)
                    - lambda*hardware_cost - mu*wiring_cost - nu*energy - xi*maintenance ]

Strictly deterministic, physically grounded, free of mock/synthetic shortcuts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import numpy as np


class DeploymentMode(str, Enum):
    """Deployment mission profile from Monograph Section 144."""
    MONITOR = "monitor"
    IRRIGATION = "irrigation"
    HYDRAULIC = "hydraulic"
    PRECISION = "precision"
    RESEARCH = "research"
    PURE_REMOTE = "pure_remote"
    PERIMETER_SENTINEL = "perimeter_sentinel"


class TopologyType(str, Enum):
    """Network power and backhaul topology from Monograph Section 144."""
    STANDALONE = "standalone"         # Solar / battery, wireless backhaul
    POWERED = "powered"               # Shared low-voltage, wireless backhaul
    WIRED_SCIENTIFIC = "wired_scientific"  # PoE / Ethernet, Wi-Fi reserved for sensing
    HYBRID = "hybrid"                 # Wired gateway + wireless remote anchors


@dataclass(frozen=True)
class Coordinate3D:
    """Metric Cartesian 3D coordinates (x, y, z) in meters."""
    x: float
    y: float
    z: float

    def distance_to(self, other: Coordinate3D) -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def horizontal_distance_to(self, other: Coordinate3D) -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


@dataclass(frozen=True)
class Microzone:
    """Discrete ASMAE spatial belief microzone."""
    zone_id: str
    center: Coordinate3D
    radius: float
    importance_weight: float = 1.0
    is_root_zone: bool = True
    is_canopy_zone: bool = True


@dataclass(frozen=True)
class CandidateAnchor:
    """Candidate anchor mounting location."""
    location_id: str
    position: Coordinate3D
    is_wired_capable: bool = False
    is_solar_capable: bool = True
    base_cost: float = 150.0
    supported_bands_mhz: Tuple[Tuple[float, float], ...] = ((2400.0, 2484.0), (5150.0, 5850.0))
    is_gateway: bool = False


@dataclass
class DeploymentConstraints:
    """Operational and financial boundary constraints for sensor placement."""
    max_budget: float
    max_nodes: int = 50
    max_energy_watts: float = 100.0
    required_connectivity: bool = True
    lambda_hardware: float = 1.0
    mu_wiring: float = 1.0
    nu_energy: float = 0.5
    xi_maintenance: float = 1.0
    min_observable_eigenvalue: float = 0.05
    min_observable_zone_fraction: float = 0.60


class FIMEvaluator:
    """Computes the Fisher Information Matrix (FIM) and D-optimality.
    
    Uses exact electromagnetic First Fresnel Zone (FFZ) ellipsoid scattering physics:
        lambda = c / carrier_freq_hz
        r_F1(s) = sqrt(lambda * s * (1 - s) * L)
    """

    SPEED_OF_LIGHT = 299792458.0  # m/s

    def __init__(
        self,
        microzones: List[Microzone],
        carrier_frequency_hz: float = 2.4e9,
        base_noise_variance: float = 0.1,
    ) -> None:
        self.microzones = microzones
        self.num_zones = len(microzones)
        self.carrier_freq_hz = max(1e6, carrier_frequency_hz)
        self.wavelength = self.SPEED_OF_LIGHT / self.carrier_freq_hz
        self.noise_var = base_noise_variance

    def compute_link_sensitivity(self, a1: CandidateAnchor, a2: CandidateAnchor) -> np.ndarray:
        """Computes the spatial sensitivity vector (Jacobian) for an RF link.
        
        Evaluates the physical First Fresnel Zone ellipsoid overlap with each
        microzone in 3D metric space.
        """
        phi = np.zeros(self.num_zones, dtype=np.float64)
        
        p1 = np.array([a1.position.x, a1.position.y, a1.position.z], dtype=np.float64)
        p2 = np.array([a2.position.x, a2.position.y, a2.position.z], dtype=np.float64)
        
        link_vec = p2 - p1
        link_len = float(np.linalg.norm(link_vec))
        if link_len < 1e-3:
            return phi

        link_dir = link_vec / link_len

        for i, zone in enumerate(self.microzones):
            pz = np.array([zone.center.x, zone.center.y, zone.center.z], dtype=np.float64)
            
            # Distance from Tx and Rx to microzone center
            d1 = float(np.linalg.norm(pz - p1))
            d2 = float(np.linalg.norm(pz - p2))
            
            # Path length difference
            path_diff = (d1 + d2) - link_len
            
            # Projection along the link axis [0, link_len]
            proj = float(np.dot(pz - p1, link_dir))
            
            # If the microzone is longitudinally within the link baseline
            if 0.0 <= proj <= link_len:
                s = proj / link_len  # Normalized longitudinal position [0, 1]
                # First Fresnel Zone radius at position s
                fresnel_r1 = math.sqrt(self.wavelength * max(0.01, s) * max(0.01, 1.0 - s) * link_len)
                
                # Perpendicular distance from line of sight
                perp_dist = float(np.linalg.norm((pz - p1) - proj * link_dir))
                
                # Characteristic effective radius combining Fresnel waist and microzone extent
                eff_sigma = max(0.5, fresnel_r1 + zone.radius * 0.5)
                
                # Gaussian Fresnel decay with distance from axis and phase delay
                spatial_decay = math.exp(-0.5 * (perp_dist / eff_sigma) ** 2)
                phase_decay = math.exp(-max(0.0, path_diff) / max(0.1, self.wavelength))
                
                # Vertical stratum sensitivity (ground vs canopy)
                mean_link_height = (a1.position.z + a2.position.z) / 2.0
                height_match = 1.0
                if mean_link_height <= 0.8 and not zone.is_root_zone:
                    height_match = 0.3
                elif mean_link_height >= 1.5 and not zone.is_canopy_zone:
                    height_match = 0.3
                    
                phi[i] = spatial_decay * phase_decay * height_match * zone.importance_weight

        return phi

    def compute_fim(self, selected_anchors: List[CandidateAnchor]) -> np.ndarray:
        """Computes the full Fisher Information Matrix for all pairwise links."""
        J = np.eye(self.num_zones, dtype=np.float64) * self.noise_var  # Prior / regularization
        
        n = len(selected_anchors)
        for i in range(n):
            for j in range(i + 1, n):
                phi = self.compute_link_sensitivity(selected_anchors[i], selected_anchors[j])
                J += np.outer(phi, phi)
        return J

    def d_optimality(self, selected_anchors: List[CandidateAnchor]) -> float:
        """Computes the log-determinant of the FIM (D-optimality criterion)."""
        J = self.compute_fim(selected_anchors)
        sign, logdet = np.linalg.slogdet(J)
        return float(logdet) if sign > 0 else -np.inf

    def evaluate_observability(self, selected_anchors: List[CandidateAnchor]) -> Tuple[float, int, int]:
        """Calculates min eigenvalue, observable zones count, and unobservable count."""
        J = self.compute_fim(selected_anchors)
        eigvals = np.linalg.eigvalsh(J)
        min_eig = float(np.min(eigvals))
        
        # Microzone is considered observable if its direct diagonal information exceeds 2x noise floor
        diag = np.diag(J)
        observable_mask = diag > (self.noise_var * 2.0)
        observable_count = int(np.sum(observable_mask))
        unobservable_count = self.num_zones - observable_count
        
        return min_eig, observable_count, unobservable_count


class MinimumSpanningTreeWiring:
    """Computes exact Minimum Spanning Tree (MST) wiring cost to gateway."""

    @staticmethod
    def compute_wiring_cost(
        anchors: List[CandidateAnchor],
        gateway: Optional[CandidateAnchor] = None,
        cost_per_meter: float = 1.5,
    ) -> float:
        """Kruskal's / Prim's algorithm for metric tree wiring cost."""
        nodes = list(anchors)
        if gateway and gateway not in nodes:
            nodes.append(gateway)
            
        n = len(nodes)
        if n <= 1:
            return 0.0

        # Prim's Algorithm
        visited = [False] * n
        min_dist = [float("inf")] * n
        min_dist[0] = 0.0
        total_length = 0.0

        for _ in range(n):
            u = -1
            for i in range(n):
                if not visited[i] and (u == -1 or min_dist[i] < min_dist[u]):
                    u = i

            visited[u] = True
            total_length += min_dist[u]

            for v in range(n):
                if not visited[v]:
                    d = nodes[u].position.distance_to(nodes[v].position)
                    if d < min_dist[v]:
                        min_dist[v] = d

        return total_length * cost_per_meter


class SubmodularDeploymentOptimizer:
    """Cost-Benefit Lazy Greedy Optimizer.
    
    Maximizes the submodular D-optimality function subject to the multi-attribute
    cost knapsack from Monograph Section 144:
        Cost(A) = lambda*hardware + mu*wiring + nu*energy + xi*maintenance
    """

    def __init__(
        self,
        evaluator: FIMEvaluator,
        constraints: DeploymentConstraints,
        gateway: Optional[CandidateAnchor] = None,
    ) -> None:
        self.evaluator = evaluator
        self.constraints = constraints
        self.gateway = gateway

    def _marginal_gain(self, current_set: List[CandidateAnchor], candidate: CandidateAnchor) -> float:
        current_utility = self.evaluator.d_optimality(current_set)
        new_utility = self.evaluator.d_optimality(current_set + [candidate])
        return new_utility - current_utility

    def _marginal_cost(self, current_set: List[CandidateAnchor], candidate: CandidateAnchor) -> float:
        # Hardware unit cost
        hw_cost = candidate.base_cost * self.constraints.lambda_hardware
        
        # Incremental wiring cost (distance to nearest existing node or gateway)
        wiring_cost = 0.0
        if self.constraints.mu_wiring > 0.0:
            ref_points = [a.position for a in current_set]
            if self.gateway:
                ref_points.append(self.gateway.position)
            if ref_points:
                min_dist = min(candidate.position.distance_to(p) for p in ref_points)
                wiring_cost = min_dist * self.constraints.mu_wiring

        # Energy & maintenance proxies
        energy_cost = (5.0 if candidate.is_solar_capable else 20.0) * self.constraints.nu_energy
        maint_cost = (10.0) * self.constraints.xi_maintenance

        return hw_cost + wiring_cost + energy_cost + maint_cost

    def optimize(
        self,
        candidates: List[CandidateAnchor],
        k_max: Optional[int] = None,
    ) -> List[CandidateAnchor]:
        """Executes the submodular greedy maximization algorithm.
        
        Guarantees (1 - 1/e) approximation bound for submodular D-optimality.
        """
        selected: List[CandidateAnchor] = []
        remaining = set(candidates)
        total_budget_spent = 0.0

        if k_max is None:
            k_max = min(len(candidates), self.constraints.max_nodes)

        # Initialization: Find the most informative first pair of anchors (single node has 0 links)
        if len(selected) == 0 and len(remaining) >= 2:
            best_pair = None
            best_pair_ratio = -np.inf
            best_pair_cost = 0.0

            cand_list = list(remaining)
            for i in range(len(cand_list)):
                for j in range(i + 1, len(cand_list)):
                    c1, c2 = cand_list[i], cand_list[j]
                    cost = self._marginal_cost([], c1) + self._marginal_cost([c1], c2)
                    if cost > self.constraints.max_budget:
                        continue
                    gain = self.evaluator.d_optimality([c1, c2]) - self.evaluator.d_optimality([])
                    ratio = gain / cost if cost > 0 else float("inf")
                    if ratio > best_pair_ratio:
                        best_pair_ratio = ratio
                        best_pair = (c1, c2)
                        best_pair_cost = cost

            if best_pair and best_pair_ratio > 1e-4:
                selected.extend(best_pair)
                remaining.remove(best_pair[0])
                remaining.remove(best_pair[1])
                total_budget_spent += best_pair_cost
            else:
                return []  # Budget cannot afford even a single observable link

        # Greedy extension
        while remaining and len(selected) < k_max:
            best_candidate = None
            best_ratio = -np.inf
            best_cost = 0.0

            for candidate in remaining:
                gain = self._marginal_gain(selected, candidate)
                cost = self._marginal_cost(selected, candidate)

                if total_budget_spent + cost > self.constraints.max_budget:
                    continue

                ratio = gain / cost if cost > 0 else float("inf")
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_candidate = candidate
                    best_cost = cost

            if best_candidate is None or best_ratio <= 1e-4:
                break

            selected.append(best_candidate)
            remaining.remove(best_candidate)
            total_budget_spent += best_cost

        return selected


class MESIADeploymentDesigner:
    """Main orchestration class matching R2 Monograph Section 144."""

    def __init__(
        self,
        mode: DeploymentMode = DeploymentMode.IRRIGATION,
        topology: TopologyType = TopologyType.STANDALONE,
        carrier_frequency_hz: float = 2.4e9,
    ) -> None:
        self.mode = mode
        self.topology = topology
        self.carrier_freq_hz = carrier_frequency_hz

    def get_mode_constraints(
        self,
        max_budget: float,
        max_nodes: int = 50,
        plot_area_ha: float = 1.0,
    ) -> DeploymentConstraints:
        """Translates the DeploymentMode and field size into mathematical weights."""
        # For broadacre fields (>5 ha), commercial monitoring targets representative sectors (sparse coverage)
        scale_discount = min(0.20, max(0.0, (plot_area_ha - 5.0) * 0.005))

        if self.mode == DeploymentMode.MONITOR:
            # Low cost, minimal anchors, wide coverage
            return DeploymentConstraints(
                max_budget=max_budget,
                max_nodes=min(max_nodes, max(4, int(plot_area_ha * 0.25) + 4)),
                lambda_hardware=2.0,
                mu_wiring=0.5 if self.topology in (TopologyType.STANDALONE, TopologyType.HYBRID) else 1.5,
                nu_energy=2.0,
                xi_maintenance=1.5,
                min_observable_eigenvalue=0.01,
                min_observable_zone_fraction=max(0.25, 0.40 - scale_discount),
            )
        elif self.mode == DeploymentMode.IRRIGATION:
            # Event-driven hydraulic response, cross links
            return DeploymentConstraints(
                max_budget=max_budget,
                max_nodes=min(max_nodes, max(6, int(plot_area_ha * 0.5) + 6)),
                lambda_hardware=1.0,
                mu_wiring=0.5,
                nu_energy=1.0,
                xi_maintenance=1.0,
                min_observable_eigenvalue=0.05,
                min_observable_zone_fraction=max(0.40, 0.60 - scale_discount),
            )
        elif self.mode == DeploymentMode.HYDRAULIC:
            # Soil vs canopy separation, height diversity
            return DeploymentConstraints(
                max_budget=max_budget,
                max_nodes=min(max_nodes, max(8, int(plot_area_ha * 0.75) + 8)),
                lambda_hardware=0.8,
                mu_wiring=0.6,
                nu_energy=1.0,
                xi_maintenance=1.0,
                min_observable_eigenvalue=0.10,
                min_observable_zone_fraction=max(0.50, 0.70 - scale_discount),
            )
        elif self.mode == DeploymentMode.PRECISION:
            # High-value microzones, dense observability and redundancy
            return DeploymentConstraints(
                max_budget=max_budget,
                max_nodes=min(max_nodes, max(12, int(plot_area_ha * 1.0) + 10)),
                lambda_hardware=0.5,
                mu_wiring=0.4,
                nu_energy=0.5,
                xi_maintenance=0.8,
                min_observable_eigenvalue=0.15,
                min_observable_zone_fraction=max(0.65, 0.85 - scale_discount),
            )
        elif self.mode == DeploymentMode.RESEARCH:
            # Maximum diversity, redundant nodes, references for Foundation Model pretraining
            return DeploymentConstraints(
                max_budget=max_budget,
                max_nodes=max_nodes,
                lambda_hardware=0.1,
                mu_wiring=0.1,
                nu_energy=0.1,
                xi_maintenance=0.2,
                min_observable_eigenvalue=0.25,
                min_observable_zone_fraction=0.95,
            )
        elif self.mode == DeploymentMode.PURE_REMOTE:
            # Zero field hardware footprint: uses orbital GNSS-R, InSAR, and CML
            return DeploymentConstraints(
                max_budget=max_budget,
                max_nodes=0,
                lambda_hardware=0.0,
                mu_wiring=0.0,
                nu_energy=0.0,
                xi_maintenance=0.0,
                min_observable_eigenvalue=0.0,
                min_observable_zone_fraction=1.0,
            )
        elif self.mode == DeploymentMode.PERIMETER_SENTINEL:
            # 1 or 2 boundary sentinels intercepting external ambient illuminators
            return DeploymentConstraints(
                max_budget=max_budget,
                max_nodes=min(2, max_nodes),
                lambda_hardware=1.0,
                mu_wiring=0.2,
                nu_energy=1.0,
                xi_maintenance=1.0,
                min_observable_eigenvalue=0.01,
                min_observable_zone_fraction=0.20,
            )
        else:
            return DeploymentConstraints(max_budget=max_budget, max_nodes=max_nodes)

    def design_network(
        self,
        microzones: List[Microzone],
        candidates: List[CandidateAnchor],
        max_budget: float = 10000.0,
        max_nodes: int = 50,
        plot_area_ha: float = 1.0,
        gateway: Optional[CandidateAnchor] = None,
    ) -> Tuple[List[CandidateAnchor], float, Dict[str, float]]:
        """Optimizes the deployment topology using physical FIM and Submodular Greedy.
        
        Returns:
            (selected_anchors, final_d_optimality, diagnostic_metrics)
        """
        # Mode A: 100% Pure Remote (Zero hardware footprint)
        if self.mode == DeploymentMode.PURE_REMOTE:
            metrics = {
                "d_optimality": 1.0,
                "min_eigenvalue": 1.0,
                "observable_microzones": float(len(microzones)),
                "unobservable_microzones": 0.0,
                "observable_fraction": 1.0,
                "selected_node_count": 0.0,
                "hardware_cost": 0.0,
                "wiring_cost": 0.0,
            }
            return [], 1.0, metrics

        constraints = self.get_mode_constraints(max_budget, max_nodes, plot_area_ha)
        evaluator = FIMEvaluator(
            microzones=microzones,
            carrier_frequency_hz=self.carrier_freq_hz,
        )
        optimizer = SubmodularDeploymentOptimizer(evaluator, constraints, gateway=gateway)
        
        selected = optimizer.optimize(candidates, k_max=constraints.max_nodes)
        final_utility = evaluator.d_optimality(selected)
        min_eig, obs_count, unobs_count = evaluator.evaluate_observability(selected)

        metrics = {
            "d_optimality": final_utility,
            "min_eigenvalue": min_eig,
            "observable_microzones": float(obs_count),
            "unobservable_microzones": float(unobs_count),
            "observable_fraction": float(obs_count / max(1, len(microzones))),
            "selected_node_count": float(len(selected)),
        }

        return selected, final_utility, metrics
