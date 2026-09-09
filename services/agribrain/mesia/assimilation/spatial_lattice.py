"""MESIA Shared Belief Lattice & ASMAE Microzone Mapping — R6 §11.1 / P9.1.

Defines the discrete spatial voxel lattice connecting MESIA radio sensitivity
kernels to ASMAE crop/soil state representations across microzones and depth/canopy strata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class LatticeStrata(str, Enum):
    UPPER_CANOPY = "UPPER_CANOPY"              # Top foliage
    LOWER_CANOPY = "LOWER_CANOPY"              # Under-canopy trunk/stem
    SOIL_SURFACE_0_5CM = "SURFACE_0_5CM"       # 0 - 5 cm
    ROOT_ZONE_5_30CM = "ROOT_ZONE_5_30CM"      # 5 - 30 cm
    DEEP_SOIL_30_60CM = "DEEP_SOIL_30_60CM"    # 30 - 60 cm
    SUBROOT_60_100CM = "SUBROOT_60_100CM"      # 60 - 100 cm


@dataclass(frozen=True)
class MicrozoneCell:
    """Discrete spatial cell in the agricultural plot lattice."""

    microzone_id: str
    grid_x: int
    grid_y: int
    centre_east_m: float
    centre_north_m: float
    cell_width_m: float
    plot_id: str


class SharedBeliefLattice:
    """Manages spatial grid discretization and voxel mapping for ASMAE."""

    def __init__(self, plot_id: str, cell_size_m: float = 10.0, grid_dim: Tuple[int, int] = (10, 10)) -> None:
        self.plot_id = plot_id
        self.cell_size_m = cell_size_m
        self.grid_dim = grid_dim
        self._cells: Dict[str, MicrozoneCell] = {}
        self._initialize_grid()

    def _initialize_grid(self) -> None:
        nx, ny = self.grid_dim
        for i in range(nx):
            for j in range(ny):
                cell_id = f"{self.plot_id}_MZ_{i}_{j}"
                self._cells[cell_id] = MicrozoneCell(
                    microzone_id=cell_id,
                    grid_x=i,
                    grid_y=j,
                    centre_east_m=(i + 0.5) * self.cell_size_m,
                    centre_north_m=(j + 0.5) * self.cell_size_m,
                    cell_width_m=self.cell_size_m,
                    plot_id=self.plot_id,
                )

    def get_cell_for_point(self, east_m: float, north_m: float) -> Optional[MicrozoneCell]:
        """Find the microzone containing the specified local ENU coordinates."""
        i = int(east_m // self.cell_size_m)
        j = int(north_m // self.cell_size_m)
        cell_id = f"{self.plot_id}_MZ_{i}_{j}"
        return self._cells.get(cell_id)

    def list_all_cells(self) -> List[MicrozoneCell]:
        return list(self._cells.values())
