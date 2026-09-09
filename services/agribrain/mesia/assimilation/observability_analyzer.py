"""MESIA Observability Analyzer & Certificate Generator — R6 §11.3 / P9.3.

Analyzes Fisher information matrix, rank, condition number, and produces
ObservabilityCertificate records certifying exactly which microzones and strata are observable.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..contracts.scientific import ObservabilityCertificate
from .spatial_lattice import SharedBeliefLattice
from .sensitivity_kernels import LinkSensitivityProfile


class ObservabilityAnalyzer:
    """Evaluates algebraic observability over the shared spatial lattice."""

    @staticmethod
    def analyze_observability(
        certificate_id: str,
        target_capability: str,
        link_profiles: List[LinkSensitivityProfile],
        lattice: SharedBeliefLattice,
        min_weight_threshold: float = 0.5,
    ) -> ObservabilityCertificate:
        """Compute coverage overlap and information conditioning."""
        all_cells = lattice.list_all_cells()
        cell_coverage: Dict[str, float] = {c.microzone_id: 0.0 for c in all_cells}
        participating_links: List[str] = [p.link_id for p in link_profiles]

        for p in link_profiles:
            for mz_id, w in p.weights_by_microzone.items():
                if mz_id in cell_coverage:
                    cell_coverage[mz_id] += w

        supported_zones: List[str] = []
        unobservable_zones: List[str] = []

        for mz_id, total_w in cell_coverage.items():
            if total_w >= min_weight_threshold:
                supported_zones.append(mz_id)
            else:
                unobservable_zones.append(mz_id)

        num_cells = max(1, len(all_cells))
        coverage_fraction = len(supported_zones) / num_cells

        try:
            import numpy as np
            has_numpy = True
        except ImportError:
            has_numpy = False

        if has_numpy and len(link_profiles) > 0 and len(supported_zones) > 0:
            # Construct Jacobian matrix A where rows are links and cols are microzones
            zone_idx = {mz: i for i, mz in enumerate(supported_zones)}
            A = np.zeros((len(link_profiles), len(supported_zones)))
            for i, p in enumerate(link_profiles):
                for mz_id, w in p.weights_by_microzone.items():
                    if mz_id in zone_idx:
                        A[i, zone_idx[mz_id]] = w
            
            # Fisher Information Matrix = A^T * A
            FIM = np.dot(A.T, A)
            eigenvalues = np.linalg.eigvalsh(FIM)
            effective_rank = float(np.sum(eigenvalues > 1e-10))
            if effective_rank > 0 and eigenvalues[0] > 1e-10:
                condition_number = float(eigenvalues[-1] / eigenvalues[0])
            else:
                condition_number = float("inf")
            fisher_score = float(np.sum(np.diag(FIM)))
            is_observable = bool(effective_rank == len(supported_zones))
        else:
            effective_rank = float(min(len(link_profiles), len(supported_zones)))
            condition_number = float("inf")
            fisher_score = 0.0
            is_observable = False

        posterior_contraction = 0.0
        now = datetime.now(timezone.utc)

        return ObservabilityCertificate(
            certificate_id=certificate_id,
            target_capability=target_capability,
            issued_at=now,
            expires_at=None,
            supported_microzones=supported_zones,
            supported_strata=[],  # Audit Finding #8: was hard-coded ["SURFACE_0_5CM", "ROOT_ZONE_5_30CM"]
            unobservable_zones=unobservable_zones,
            unobservable_strata=[],  # Audit Finding #8: was hard-coded ["SUBROOT_60_100CM"]
            effective_rank=effective_rank,
            condition_number=condition_number,
            fisher_information_score=fisher_score,
            collinearity_index=float("inf"),  # Audit Finding #8: was hard-coded 0.12
            posterior_contraction_ratio=posterior_contraction,
            participating_links=participating_links,
            critical_links=[],  # Was arbitrary first link; requires real sensitivity analysis
            dropout_robustness_score=0.0,  # Audit Finding #8: was hard-coded 0.85
            geometry_epoch_refs=[],
            effective_spatial_resolution_m=lattice.cell_size_m,
            effective_temporal_resolution_s=0.0,  # Was hard-coded 60.0; requires real data
            depth_limit_m=0.0,  # Was hard-coded 0.30; requires real data
            is_observable=False,  # Audit Finding #6: fail-closed; was True when zones > 0
            abstention_reasons=["CONTAINMENT: observability requires real Fisher information matrix (Audit Finding #8)"],
        )
