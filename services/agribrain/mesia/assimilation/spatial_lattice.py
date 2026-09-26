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
    aliases: Tuple[str, ...] = ()

    @property
    def row(self) -> int:
        return self.grid_y

    @property
    def col(self) -> int:
        return self.grid_x


class SharedBeliefLattice:
    """Manages spatial grid discretization and voxel mapping for ASMAE."""

    def __init__(
        self,
        plot_id: str,
        cell_size_m: float = 10.0,
        grid_dim: Tuple[int, int] = (10, 10),
        origin_east_m: float = 0.0,
        origin_north_m: float = 0.0,
        crs: Optional[str] = None,
        boundary_mask: Optional[Any] = None,
        target_grid: Optional[Any] = None,
    ) -> None:
        self.plot_id = plot_id
        if target_grid is not None:
            n_rows = int(getattr(target_grid, "n_rows", grid_dim[0]))
            n_cols = int(getattr(target_grid, "n_cols", grid_dim[1]))
            self.grid_dim = (n_rows, n_cols)
            self.cell_size_m = float(getattr(target_grid, "resolution_m", cell_size_m) or cell_size_m)
            self.origin_east_m = float(getattr(target_grid, "origin_x", origin_east_m) or origin_east_m)
            self.origin_north_m = float(getattr(target_grid, "origin_y", origin_north_m) or origin_north_m)
            self.crs = str(getattr(target_grid, "crs", crs or "EPSG:32631"))
        else:
            self.cell_size_m = float(cell_size_m)
            self.grid_dim = grid_dim
            self.origin_east_m = float(origin_east_m)
            self.origin_north_m = float(origin_north_m)
            self.crs = crs
        self.boundary_mask = boundary_mask
        self.target_grid = target_grid
        self._cells: Dict[str, MicrozoneCell] = {}
        self._unique_cells: List[MicrozoneCell] = []
        self._initialize_grid()

    def _initialize_grid(self) -> None:
        n_rows, n_cols = self.grid_dim
        for r in range(n_rows):
            for c in range(n_cols):
                primary_id = f"mz_{r:03d}_{c:03d}"
                aliases = (
                    f"{self.plot_id}_MZ_{c}_{r}",
                    f"MZ_{c}_{r}",
                    f"{self.plot_id}_mz_{r:03d}_{c:03d}",
                )
                cell = MicrozoneCell(
                    microzone_id=primary_id,
                    grid_x=c,
                    grid_y=r,
                    centre_east_m=self.origin_east_m + (c + 0.5) * self.cell_size_m,
                    centre_north_m=self.origin_north_m + (r + 0.5) * self.cell_size_m,
                    cell_width_m=self.cell_size_m,
                    plot_id=self.plot_id,
                    aliases=aliases,
                )
                self._unique_cells.append(cell)
                self._cells[primary_id] = cell
                for a in aliases:
                    self._cells[a] = cell

    def get_cell(self, cell_ref: str) -> Optional[MicrozoneCell]:
        """Find a cell by its canonical ID or any registered alias."""
        return self._cells.get(cell_ref)

    def get_cell_for_point(self, east_m: float, north_m: float) -> Optional[MicrozoneCell]:
        """Find the microzone containing the specified local ENU coordinates."""
        rel_e = east_m - self.origin_east_m if east_m >= self.origin_east_m else east_m
        rel_n = north_m - self.origin_north_m if north_m >= self.origin_north_m else north_m
        c = int(rel_e // self.cell_size_m)
        r = int(rel_n // self.cell_size_m)
        n_rows, n_cols = self.grid_dim
        if 0 <= r < n_rows and 0 <= c < n_cols:
            primary_id = f"mz_{r:03d}_{c:03d}"
            return self._cells.get(primary_id)
        return None

    def list_all_cells(self) -> List[MicrozoneCell]:
        return list(self._unique_cells)
