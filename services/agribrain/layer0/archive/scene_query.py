"""
Geographic query translation helpers.
"""
from typing import Dict, Any, List

def calculate_aoi_footprint(geometry_wkt: str) -> Dict[str, Any]:
    """Calculates coordinate extent/envelope of plot footprint."""
    return {"wkt": geometry_wkt, "type": "Polygon"}

def check_tile_overlap(tile_footprint: str, plot_geometry: str) -> float:
    """Computes basic overlap fraction between the scene and the plot."""
    # Synthetic/stub overlap checker
    if not tile_footprint or not plot_geometry:
        return 0.0
    return 1.0 # full overlap by default for stubs
