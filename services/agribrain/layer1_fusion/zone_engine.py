"""
Layer 1.2: Management Zone Engine
Clusters field-level spatial data (NDVI, SAR) into stable management zones.
This is the heart of AgriBrain's Polygon-Aware Spatial Intelligence.
"""

from typing import Dict, List, Any, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

def generate_management_zones(
    plot_id: str, 
    ndvi_stack: List[List[List[float]]], # [Time, Height, Width]
    sar_vv_stack: List[List[List[float]]],
    grid_spec: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Computes stable management zones across the field grid.
    Uses a robust quantile-based slicing logic on the temporal median 
    to separate the field into High, Medium, and Low vigor zones.
    
    Returns:
        Dict: mapping of zone_id -> {
            "label": "High Vigor Zone",
            "area_pct": 33.3,
            "mask": List[List[int]] (1 if cell is in zone, 0 otherwise),
            "centroid": [lat, lng] approximation,
            "signature": {"ndvi_median": 0.65, "sar_vv_median": -10.2}
        }
    """
    print(f"🌍 [Zone Engine] Generating Management Zones for {plot_id}")
    
    if not ndvi_stack or not ndvi_stack[0]:
        print("⚠️ [Zone Engine] No NDVI spatial data found. Defaulting to Single Zone.")
        return _fallback_single_zone(grid_spec)
        
    # 1. Convert to Numpy arrays for spatial math
    ndvi_np = np.array(ndvi_stack, dtype=float) # Shape: [T, H, W]
    sar_np = np.array(sar_vv_stack, dtype=float) if sar_vv_stack else None
    
    H, W = ndvi_np.shape[1], ndvi_np.shape[2]
    total_cells = H * W
    
    # Map None/NaN to np.nan explicitly
    ndvi_np[ndvi_np == None] = np.nan
    
    # 2. Compute Temporal Medians across the stack (ignore nans)
    # Using nanmedian to ignore cloudy days
    with np.errstate(all='ignore'):
        ndvi_median_map = np.nanmedian(ndvi_np, axis=0)
    
    # If the entire map is NaN (clouds for 60 days straight), fallback
    if np.all(np.isnan(ndvi_median_map)):
        print("🌧️ [Zone Engine] NDVI map is entirely obscured (clouds). Fallback to Single Zone.")
        return _fallback_single_zone(grid_spec)
        
    # 3. Quantile Segmentation (Top 33%, Middle 33%, Bottom 33%)
    # Only consider valid pixels for quantiles
    valid_ndvi = ndvi_median_map[~np.isnan(ndvi_median_map)]
    
    # Handle homogeneous fields (very tightly clustered values)
    if len(valid_ndvi) < 4 or np.std(valid_ndvi) < 0.02:
         print("🟩 [Zone Engine] Field is highly homogeneous. Emitting Single Zone.")
         return _fallback_single_zone(grid_spec)
         
    p66 = np.percentile(valid_ndvi, 66.6)
    p33 = np.percentile(valid_ndvi, 33.3)
    
    # 4. Create Spatial Masks
    zone_masks = {
        "Zone A": (ndvi_median_map >= p66).astype(int),
        "Zone B": ((ndvi_median_map >= p33) & (ndvi_median_map < p66)).astype(int),
        "Zone C": (ndvi_median_map < p33).astype(int)
    }
    
    labels = {
        "Zone A": "High Vigor Zone",
        "Zone B": "Average Vigor Zone",
        "Zone C": "Lagging / Stress Zone"
    }
    
    zones_output = {}
    
    # 5. Compile Output Artifact
    for z_id, mask in zone_masks.items():
        cell_count = np.sum(mask)
        area_pct = round((cell_count / total_cells) * 100, 1)
        
        # Calculate cluster signatures
        z_ndvi_median = np.nanmedian(ndvi_median_map[mask == 1]) if cell_count > 0 else 0.0
        
        signature = {"ndvi_median": float(z_ndvi_median)}
        
        if sar_np is not None:
             with np.errstate(all='ignore'):
                 sar_median_map = np.nanmedian(sar_np, axis=0)
                 z_sar_median = np.nanmedian(sar_median_map[mask == 1]) if cell_count > 0 else 0.0
                 signature["sar_vv_median"] = float(z_sar_median)
                 
        # Centroid Approximation (Grid Index)
        y_idx, x_idx = np.where(mask == 1)
        centroid = [float(np.mean(y_idx)), float(np.mean(x_idx))] if len(y_idx) > 0 else [0, 0]
        
        zones_output[z_id] = {
            "label": labels[z_id],
            "area_pct": area_pct,
            "mask": mask.tolist(),
            "centroid": centroid,
            "signature": signature
        }
        
    print(f"✅ [Zone Engine] Built 3 Zones (A: {zones_output['Zone A']['area_pct']}%, B: {zones_output['Zone B']['area_pct']}%, C: {zones_output['Zone C']['area_pct']}%)")
    return zones_output

def compute_zone_stats(
    ndvi_stack: List[List[List[float]]],
    sar_vv_stack: List[List[List[float]]],
    zones: Dict[str, Dict[str, Any]],
    time_index: List[str]
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Computes daily timeseries statistics for each management zone.
    Returns:
        Dict: variable -> {zone_id -> [{"date": "2024-01-01", "mean": 0.5, "std": 0.05}]}
    """
    print("📈 [Zone Engine] Computing zonal statistics across time...")
    
    if not zones:
        return {}
        
    ndvi_np = np.array(ndvi_stack, dtype=float)
    sar_np = np.array(sar_vv_stack, dtype=float) if sar_vv_stack else None
    
    # Map None values
    ndvi_np = np.where(ndvi_np == None, np.nan, ndvi_np)
    if sar_np is not None:
        sar_np = np.where(sar_np == None, np.nan, sar_np)
        
    stats = {
        "ndvi": {},
        "sar_vv": {}
    }
    
    T = len(time_index)
    
    for z_id, z_data in zones.items():
        mask = np.array(z_data["mask"])
        stats["ndvi"][z_id] = []
        stats["sar_vv"][z_id] = []
        
        for t in range(min(T, ndvi_np.shape[0])):
            date_str = time_index[t]
            
            # --- NDVI Zonal Stats ---
            day_ndvi = ndvi_np[t]
            zonal_ndvi_pixels = day_ndvi[mask == 1]
            valid_ndvi = zonal_ndvi_pixels[~np.isnan(zonal_ndvi_pixels)]
            
            if len(valid_ndvi) > 0:
                stats["ndvi"][z_id].append({
                    "date": date_str,
                    "mean": float(np.mean(valid_ndvi)),
                    "std": float(np.std(valid_ndvi)),
                    "min": float(np.min(valid_ndvi)),
                    "max": float(np.max(valid_ndvi))
                })
            else:
                stats["ndvi"][z_id].append({
                    "date": date_str, "mean": None, "std": None, "min": None, "max": None
                })
                
            # --- SAR Zonal Stats ---
            if sar_np is not None and t < sar_np.shape[0]:
                day_sar = sar_np[t]
                zonal_sar_pixels = day_sar[mask == 1]
                valid_sar = zonal_sar_pixels[~np.isnan(zonal_sar_pixels)]
                
                if len(valid_sar) > 0:
                    stats["sar_vv"][z_id].append({
                        "date": date_str,
                        "mean": float(np.mean(valid_sar)),
                        "std": float(np.std(valid_sar))
                    })
                else:
                    stats["sar_vv"][z_id].append({
                        "date": date_str, "mean": None, "std": None
                    })
                    
    return stats


def _fallback_single_zone(grid_spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Generates a single monolithic zone covering 100% of the field."""
    width = grid_spec.get("width", 10)
    height = grid_spec.get("height", 10)
    
    mask = [[1] * width for _ in range(height)]
    
    return {
        "Zone A": {
            "label": "Homogeneous Field",
            "area_pct": 100.0,
            "mask": mask,
            "centroid": [height/2.0, width/2.0],
            "signature": {"ndvi_median": 0.0},
            "spatial_label": "entire field"
        }
    }


# ============================================================================
# PURE PYTHON FALLBACK (No numpy required)
# ============================================================================

def _py_median(values: List[float]) -> float:
    """Compute median without numpy."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _py_mean(values: List[float]) -> float:
    """Compute mean without numpy."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _py_std(values: List[float]) -> float:
    """Compute standard deviation without numpy."""
    if len(values) < 2:
        return 0.0
    m = _py_mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return variance ** 0.5


def _py_percentile(sorted_values: List[float], pct: float) -> float:
    """Compute percentile from sorted list without numpy."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    k = (pct / 100.0) * (n - 1)
    f = int(k)
    c = f + 1 if f + 1 < n else f
    d = k - f
    return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])


def _get_spatial_label(y: int, x: int, H: int, W: int) -> str:
    """Convert grid position to human-readable spatial descriptor."""
    v = "north" if y < H / 3 else ("south" if y >= 2 * H / 3 else "central")
    h = "west" if x < W / 3 else ("east" if x >= 2 * W / 3 else "central")
    if v == "central" and h == "central":
        return "center"
    if v == "central":
        return h
    if h == "central":
        return v
    return f"{v}-{h}"


def generate_management_zones_pure_python(
    plot_id: str,
    ndvi_stack: List[List[List[float]]],  # [Time, Height, Width]
    sar_vv_stack: List[List[List[float]]],
    grid_spec: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Pure Python management zone engine — no numpy required.
    
    Computes temporal median NDVI per pixel, then segments into 3 zones
    (High Vigor / Average / Lagging) using percentile thresholds.
    Labels each zone with a spatial descriptor (north-east, south-west, etc).
    
    Returns same schema as numpy version for seamless integration.
    """
    print(f"🌍 [Zone Engine PP] Generating Management Zones for {plot_id} (Pure Python)")
    
    if not ndvi_stack or not ndvi_stack[0]:
        print("⚠️ [Zone Engine PP] No NDVI spatial data found. Defaulting to Single Zone.")
        return _fallback_single_zone_pp(grid_spec)
    
    T = len(ndvi_stack)
    H = len(ndvi_stack[0])
    W = len(ndvi_stack[0][0]) if H > 0 else 0
    total_cells = H * W
    
    if total_cells == 0:
        return _fallback_single_zone_pp(grid_spec)
    
    # 1. Compute Temporal Median NDVI per pixel
    ndvi_median_map: List[List[float]] = []
    all_valid_medians: List[float] = []
    
    for y in range(H):
        row_medians = []
        for x in range(W):
            pixel_values = []
            for t in range(T):
                try:
                    v = ndvi_stack[t][y][x]
                    if v is not None and v == v:  # not None and not NaN
                        pixel_values.append(float(v))
                except (IndexError, TypeError):
                    pass
            
            med = _py_median(pixel_values) if pixel_values else 0.0
            row_medians.append(med)
            if pixel_values:
                all_valid_medians.append(med)
        ndvi_median_map.append(row_medians)
    
    # 2. Check for homogeneous fields
    if len(all_valid_medians) < 4 or _py_std(all_valid_medians) < 0.005:
        print("🟩 [Zone Engine PP] Field is highly homogeneous. Emitting Single Zone.")
        return _fallback_single_zone_pp(grid_spec)
    
    # 3. Percentile Segmentation (Top 33%, Middle 33%, Bottom 33%)
    sorted_medians = sorted(all_valid_medians)
    p66 = _py_percentile(sorted_medians, 66.6)
    p33 = _py_percentile(sorted_medians, 33.3)
    
    # 4. Create Spatial Masks + Cluster Signatures
    zone_defs = {
        "Zone A": {"label": "High Vigor Zone", "test": lambda v: v >= p66},
        "Zone B": {"label": "Average Vigor Zone", "test": lambda v: p33 <= v < p66},
        "Zone C": {"label": "Lagging / Stress Zone", "test": lambda v: v < p33},
    }
    
    zones_output = {}
    
    for z_id, z_def in zone_defs.items():
        mask: List[List[int]] = []
        zone_ndvi_values: List[float] = []
        zone_sar_values: List[float] = []
        y_positions: List[int] = []
        x_positions: List[int] = []
        cell_count = 0
        
        for y in range(H):
            mask_row = []
            for x in range(W):
                v = ndvi_median_map[y][x]
                if z_def["test"](v):
                    mask_row.append(1)
                    cell_count += 1
                    zone_ndvi_values.append(v)
                    y_positions.append(y)
                    x_positions.append(x)
                    
                    # Collect SAR if available
                    if sar_vv_stack:
                        sar_pixel_vals = []
                        for t in range(T):
                            try:
                                sv = sar_vv_stack[t][y][x]
                                if sv is not None and sv == sv:
                                    sar_pixel_vals.append(float(sv))
                            except (IndexError, TypeError):
                                pass
                        if sar_pixel_vals:
                            zone_sar_values.append(_py_median(sar_pixel_vals))
                else:
                    mask_row.append(0)
            mask.append(mask_row)
        
        area_pct = round((cell_count / total_cells) * 100, 1) if total_cells > 0 else 0.0
        
        # Signature
        signature = {"ndvi_median": round(_py_median(zone_ndvi_values), 4) if zone_ndvi_values else 0.0}
        if zone_sar_values:
            signature["sar_vv_median"] = round(_py_median(zone_sar_values), 2)
        
        # Centroid
        centroid_y = _py_mean(y_positions) if y_positions else H / 2.0
        centroid_x = _py_mean(x_positions) if x_positions else W / 2.0
        
        # Spatial label (human-readable)
        spatial_label = _get_spatial_label(int(centroid_y), int(centroid_x), H, W)
        
        zones_output[z_id] = {
            "label": z_def["label"],
            "area_pct": area_pct,
            "mask": mask,
            "centroid": [round(centroid_y, 1), round(centroid_x, 1)],
            "signature": signature,
            "spatial_label": spatial_label
        }
    
    print(f"✅ [Zone Engine PP] Built 3 Zones: "
          f"A({zones_output['Zone A']['spatial_label']}, {zones_output['Zone A']['area_pct']}%), "
          f"B({zones_output['Zone B']['spatial_label']}, {zones_output['Zone B']['area_pct']}%), "
          f"C({zones_output['Zone C']['spatial_label']}, {zones_output['Zone C']['area_pct']}%)")
    return zones_output


def compute_zone_stats_pure_python(
    ndvi_stack: List[List[List[float]]],
    sar_vv_stack: List[List[List[float]]],
    zones: Dict[str, Dict[str, Any]],
    time_index: List[str]
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Computes daily timeseries statistics for each management zone.
    Pure Python version — no numpy required.
    """
    print("📈 [Zone Engine PP] Computing zonal statistics across time...")
    
    if not zones:
        return {}
    
    T = len(time_index)
    
    stats: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        "ndvi": {},
        "sar_vv": {}
    }
    
    for z_id, z_data in zones.items():
        mask = z_data["mask"]
        H = len(mask)
        W = len(mask[0]) if H > 0 else 0
        
        stats["ndvi"][z_id] = []
        stats["sar_vv"][z_id] = []
        
        for t in range(min(T, len(ndvi_stack))):
            date_str = time_index[t]
            
            # --- NDVI Zonal Stats ---
            ndvi_vals = []
            for y in range(H):
                for x in range(W):
                    if mask[y][x] == 1:
                        try:
                            v = ndvi_stack[t][y][x]
                            if v is not None and v == v:
                                ndvi_vals.append(float(v))
                        except (IndexError, TypeError):
                            pass
            
            if ndvi_vals:
                stats["ndvi"][z_id].append({
                    "date": date_str,
                    "mean": round(_py_mean(ndvi_vals), 4),
                    "std": round(_py_std(ndvi_vals), 4),
                    "min": round(min(ndvi_vals), 4),
                    "max": round(max(ndvi_vals), 4)
                })
            else:
                stats["ndvi"][z_id].append({
                    "date": date_str, "mean": None, "std": None, "min": None, "max": None
                })
            
            # --- SAR Zonal Stats ---
            if sar_vv_stack and t < len(sar_vv_stack):
                sar_vals = []
                for y in range(H):
                    for x in range(W):
                        if mask[y][x] == 1:
                            try:
                                sv = sar_vv_stack[t][y][x]
                                if sv is not None and sv == sv:
                                    sar_vals.append(float(sv))
                            except (IndexError, TypeError):
                                pass
                
                if sar_vals:
                    stats["sar_vv"][z_id].append({
                        "date": date_str,
                        "mean": round(_py_mean(sar_vals), 2),
                        "std": round(_py_std(sar_vals), 2)
                    })
                else:
                    stats["sar_vv"][z_id].append({
                        "date": date_str, "mean": None, "std": None
                    })
    
    return stats


def _fallback_single_zone_pp(grid_spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Generates a single monolithic zone covering 100% of the field (Pure Python)."""
    width = grid_spec.get("width", 10)
    height = grid_spec.get("height", 10)
    
    mask = [[1] * width for _ in range(height)]
    
    return {
        "Zone A": {
            "label": "Homogeneous Field",
            "area_pct": 100.0,
            "mask": mask,
            "centroid": [height/2.0, width/2.0],
            "signature": {"ndvi_median": 0.0},
            "spatial_label": "entire field"
        }
    }


# ============================================================================
# MASK → GEOJSON CONVERTER
# Converts pixel-level binary masks to real GeoJSON zone geometries
# ============================================================================

def _mask_cell_to_rect(
    y: int, x: int,
    H: int, W: int,
    bbox: Tuple
) -> List[List[float]]:
    """
    Convert a single grid cell (y, x) to a lat/lng rectangle polygon.
    Returns [[lng, lat], ...] ring (5 coordinates, closed).
    """
    if not bbox or bbox == (0, 0, 0, 0):
        return []
    
    min_lng, min_lat, max_lng, max_lat = bbox
    lat_step = (max_lat - min_lat) / max(H, 1)
    lng_step = (max_lng - min_lng) / max(W, 1)
    
    # Cell corners (top-left origin: y=0 is top/north)
    top_lat = max_lat - y * lat_step
    bot_lat = max_lat - (y + 1) * lat_step
    left_lng = min_lng + x * lng_step
    right_lng = min_lng + (x + 1) * lng_step
    
    # GeoJSON ring: [lng, lat] order, closed polygon
    return [
        [left_lng, top_lat],
        [right_lng, top_lat],
        [right_lng, bot_lat],
        [left_lng, bot_lat],
        [left_lng, top_lat],
    ]


def masks_to_geojson(
    zones: Dict[str, Dict[str, Any]],
    polygon_coords: List[List[float]] = None,
) -> Dict[str, Any]:
    """
    Convert H×W binary zone masks to GeoJSON MultiPolygon geometries.
    
    Each zone's mask (List[List[int]]) is converted to a set of lat/lng
    rectangles assembled into a GeoJSON MultiPolygon. This produces
    data-driven zone shapes that follow actual NDVI/driver patterns.
    
    Args:
        zones: Zone dict with "mask" field (H×W binary grid)
        polygon_coords: [[lng, lat], ...] field polygon for geo-referencing
    
    Returns:
        Dict mapping zone_key → GeoJSON Feature with geometry
    """
    if not polygon_coords:
        print("⚠️ [GeoJSON] No polygon coords — cannot generate zone geometries")
        return {}
    
    bbox = _compute_polygon_bbox(polygon_coords)
    if bbox == (0, 0, 0, 0):
        return {}
    
    result = {}
    
    for z_id, z_data in zones.items():
        mask = z_data.get("mask", [])
        if not mask or not mask[0]:
            continue
        
        H = len(mask)
        W = len(mask[0])
        
        # Collect all mask=1 cells as individual polygon rings
        cell_polygons = []
        for y in range(H):
            for x in range(W):
                if mask[y][x] == 1:
                    ring = _mask_cell_to_rect(y, x, H, W, bbox)
                    if ring:
                        cell_polygons.append([ring])
        
        if not cell_polygons:
            continue
        
        # Build GeoJSON Feature
        result[z_id] = {
            "type": "Feature",
            "properties": {
                "zone_key": z_id,
                "label": z_data.get("label", z_id),
                "area_pct": z_data.get("area_pct", 0),
                "spatial_label": z_data.get("spatial_label", "center"),
                "ndvi_median": z_data.get("signature", {}).get("ndvi_median", 0),
            },
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": cell_polygons,
            }
        }
    
    zone_count = len(result)
    total_cells = sum(
        sum(1 for y in range(len(z.get("mask", [])))
            for x in range(len(z.get("mask", [[]])[0]))
            if z.get("mask", [[]])[y][x] == 1)
        for z in zones.values()
    )
    print(f"✅ [GeoJSON] Generated {zone_count} zone geometries ({total_cells} cells)")
    return result


def inject_zone_geometries(
    zones: Dict[str, Dict[str, Any]],
    polygon_coords: List[List[float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Enrich zone output with GeoJSON geometry field.
    Called after zone generation to add 'geometry' to each zone.
    """
    geojson_map = masks_to_geojson(zones, polygon_coords)
    
    for z_id, z_data in zones.items():
        if z_id in geojson_map:
            z_data["geometry"] = geojson_map[z_id]
        else:
            z_data["geometry"] = None
    
    return zones


# ============================================================================
# RESEARCH-GRADE: ZoneStats Builder (Phase A)
# Bridges raw zone output → canonical ZoneStats objects
# ============================================================================

def build_spatial_zone_stats(
    zones: Dict[str, Dict[str, Any]],
    ndvi_stack: List[List[List[float]]],
    sar_vv_stack: List[List[List[float]]],
    grid_spec: Dict[str, Any],
    polygon_coords: List[List[float]] = None,
    soil_static: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Convert raw zone output + pixel stacks into research-grade ZoneStats dicts.
    
    Each zone gets:
    - Per-feature: mean, p10, p90, std
    - Per-feature: valid_fraction, uncertainty_mean, uncertainty_p90
    - Polygon-aware: centroid in lat/lng, spatial_label from real coordinates
    
    Args:
        zones: Raw zone output from generate_management_zones_pure_python
        ndvi_stack: [T, H, W] NDVI pixel data
        sar_vv_stack: [T, H, W] SAR VV pixel data
        grid_spec: Grid specification dict
        polygon_coords: [[lng, lat], ...] from plot GeoJSON
        soil_static: Dict with soil_clay_mean, soil_sand_mean, etc.
    
    Returns:
        List of ZoneStats-compatible dicts
    """
    if not zones:
        return []
    
    T = len(ndvi_stack) if ndvi_stack else 0
    
    # Compute polygon bbox for coordinate mapping
    bbox = _compute_polygon_bbox(polygon_coords) if polygon_coords else None
    cell_size = grid_spec.get("resolution", grid_spec.get("cell_size_m", 10.0))
    H = grid_spec.get("height", 10)
    W = grid_spec.get("width", 10)
    
    zone_stats_list = []
    zone_idx = 0
    
    zone_labels_map = {
        "High Vigor Zone": "HIGH_VIGOR",
        "Average Vigor Zone": "MED_VIGOR",
        "Lagging / Stress Zone": "LOW_VIGOR",
        "Homogeneous Field": "HOMOGENEOUS",
    }
    
    for z_id, z_data in zones.items():
        mask = z_data.get("mask", [])
        area_pct = z_data.get("area_pct", 0)
        raw_label = z_data.get("label", "Unknown")
        centroid_grid = z_data.get("centroid", [H/2, W/2])
        
        # --- Collect all pixel values per feature for this zone ---
        ndvi_vals = []
        sar_vals = []
        
        for y in range(len(mask)):
            for x in range(len(mask[0]) if mask else 0):
                if mask[y][x] == 1:
                    # Collect temporal median for NDVI
                    pixel_ndvi = []
                    for t in range(T):
                        try:
                            v = ndvi_stack[t][y][x]
                            if v is not None and v == v:
                                pixel_ndvi.append(float(v))
                        except (IndexError, TypeError):
                            pass
                    if pixel_ndvi:
                        ndvi_vals.append(_py_median(pixel_ndvi))
                    
                    # Collect temporal median for SAR
                    if sar_vv_stack:
                        pixel_sar = []
                        for t in range(min(T, len(sar_vv_stack))):
                            try:
                                sv = sar_vv_stack[t][y][x]
                                if sv is not None and sv == sv:
                                    pixel_sar.append(float(sv))
                            except (IndexError, TypeError):
                                pass
                        if pixel_sar:
                            sar_vals.append(_py_median(pixel_sar))
        
        # --- Compute per-feature stats ---
        feature_means = {}
        feature_p10 = {}
        feature_p90 = {}
        feature_std = {}
        valid_fraction = {}
        uncertainty_mean = {}
        uncertainty_p90 = {}
        
        total_pixels = sum(1 for row in mask for cell in row if cell == 1) if mask else 1
        
        # NDVI
        if ndvi_vals:
            sorted_ndvi = sorted(ndvi_vals)
            feature_means["NDVI"] = _py_mean(ndvi_vals)
            feature_p10["NDVI"] = _py_percentile(sorted_ndvi, 10)
            feature_p90["NDVI"] = _py_percentile(sorted_ndvi, 90)
            feature_std["NDVI"] = _py_std(ndvi_vals)
            valid_fraction["NDVI"] = len(ndvi_vals) / max(total_pixels, 1)
            # Uncertainty: proxy from std + missing fraction
            unc_base = feature_std["NDVI"] * 0.5
            missing_penalty = (1.0 - valid_fraction["NDVI"]) * 0.1
            uncertainty_mean["NDVI"] = unc_base + missing_penalty
            uncertainty_p90["NDVI"] = (feature_p90["NDVI"] - feature_p10["NDVI"]) * 0.3
        
        # SAR
        if sar_vals:
            sorted_sar = sorted(sar_vals)
            feature_means["SAR_VV"] = _py_mean(sar_vals)
            feature_p10["SAR_VV"] = _py_percentile(sorted_sar, 10)
            feature_p90["SAR_VV"] = _py_percentile(sorted_sar, 90)
            feature_std["SAR_VV"] = _py_std(sar_vals)
            valid_fraction["SAR_VV"] = len(sar_vals) / max(total_pixels, 1)
            uncertainty_mean["SAR_VV"] = feature_std["SAR_VV"] * 0.5
            uncertainty_p90["SAR_VV"] = (feature_p90["SAR_VV"] - feature_p10["SAR_VV"]) * 0.3
        
        # Soil (from static data — same for all zones, but with resolution penalty)
        if soil_static:
            for soil_key, feature_name in [
                ("soil_clay_mean", "SOIL_CLAY"),
                ("soil_sand_mean", "SOIL_SAND"),
                ("soil_ph_mean", "SOIL_PH"),
                ("soil_org_c_mean", "SOIL_OC"),
            ]:
                val = soil_static.get(soil_key)
                if val is not None:
                    feature_means[feature_name] = float(val)
                    feature_p10[feature_name] = float(val) * 0.9  # proxy spread
                    feature_p90[feature_name] = float(val) * 1.1
                    feature_std[feature_name] = float(val) * 0.05
                    valid_fraction[feature_name] = 0.5  # SoilGrids is coarse = 50% confidence
                    uncertainty_mean[feature_name] = float(val) * 0.15  # 15% uncertainty for 250m proxy
                    uncertainty_p90[feature_name] = float(val) * 0.25
        
        # --- Compute polygon-aware centroid ---
        centroid_lat, centroid_lng = _grid_to_latlon(
            centroid_grid[0], centroid_grid[1], H, W, bbox
        )
        
        # Compute spatial label from lat/lng relative to polygon center
        spatial_label = z_data.get("spatial_label", "center")
        if bbox and polygon_coords:
            spatial_label = _latlon_spatial_label(
                centroid_lat, centroid_lng, bbox
            )
        
        # --- Compute area_m2 ---
        area_m2 = (area_pct / 100.0) * total_pixels * (cell_size ** 2)
        
        # --- Build notes ---
        notes = []
        if raw_label == "Lagging / Stress Zone":
            notes.append("Lowest NDVI — potential stress indicator")
        if feature_means.get("NDVI", 0) < 0.15:
            notes.append("Very low vegetation reflectance")
        if valid_fraction.get("SAR_VV", 1.0) < 0.3:
            notes.append("SAR coverage sparse — moisture estimates uncertain")
        
        zone_stats_list.append({
            "zone_id": zone_idx,
            "zone_key": z_id,
            "zone_label": zone_labels_map.get(raw_label, "UNKNOWN"),
            "spatial_label": spatial_label,
            "area_m2": round(area_m2, 1),
            "area_pct": area_pct,
            "centroid_lat": round(centroid_lat, 6),
            "centroid_lng": round(centroid_lng, 6),
            "feature_means": {k: round(v, 4) for k, v in feature_means.items()},
            "feature_p10": {k: round(v, 4) for k, v in feature_p10.items()},
            "feature_p90": {k: round(v, 4) for k, v in feature_p90.items()},
            "feature_std": {k: round(v, 4) for k, v in feature_std.items()},
            "valid_fraction": {k: round(v, 3) for k, v in valid_fraction.items()},
            "uncertainty_mean": {k: round(v, 4) for k, v in uncertainty_mean.items()},
            "uncertainty_p90": {k: round(v, 4) for k, v in uncertainty_p90.items()},
            "notes": notes,
        })
        zone_idx += 1
    
    print(f"📊 [Zone Engine] Built ZoneStats for {len(zone_stats_list)} zones")
    return zone_stats_list


def _compute_polygon_bbox(coords: Any) -> Tuple:
    """Compute bounding box from polygon coordinates [[lng, lat], ...] or GeoJSON dict."""
    if not coords:
        return (0, 0, 0, 0)
        
    actual_coords = coords
    if isinstance(coords, dict):
        if "coordinates" in coords:
            if coords["type"] == "Polygon":
                actual_coords = coords["coordinates"][0]
            elif coords["type"] == "MultiPolygon":
                actual_coords = coords["coordinates"][0][0]
        else:
            return (0, 0, 0, 0)
            
    if not actual_coords or not isinstance(actual_coords, list) or len(actual_coords) == 0:
         return (0, 0, 0, 0)
         
    try:
        lngs = [float(c[0]) for c in actual_coords]
        lats = [float(c[1]) for c in actual_coords]
        return (min(lngs), min(lats), max(lngs), max(lats))
    except (IndexError, TypeError, ValueError):
        return (0, 0, 0, 0)


def _grid_to_latlon(
    grid_y: float, grid_x: float,
    H: int, W: int,
    bbox: Any
) -> Tuple[float, float]:
    """Convert grid coordinates to approximate lat/lng using polygon bbox."""
    if not bbox or bbox == (0, 0, 0, 0):
        return (0.0, 0.0)
    
    min_lng, min_lat, max_lng, max_lat = bbox
    
    # Linear interpolation within bbox
    lat = max_lat - (grid_y / max(H - 1, 1)) * (max_lat - min_lat)
    lng = min_lng + (grid_x / max(W - 1, 1)) * (max_lng - min_lng)
    
    return (lat, lng)


def _latlon_spatial_label(
    lat: float, lng: float,
    bbox: Any
) -> str:
    """Determine spatial label (north-west, south-east, etc.) from lat/lng within bbox."""
    if not bbox or bbox == (0, 0, 0, 0):
        return "center"
    
    min_lng, min_lat, max_lng, max_lat = bbox
    
    lat_range = max_lat - min_lat
    lng_range = max_lng - min_lng
    
    if lat_range == 0 and lng_range == 0:
        return "center"
    
    # Normalize position to 0..1
    lat_norm = (lat - min_lat) / lat_range if lat_range > 0 else 0.5
    lng_norm = (lng - min_lng) / lng_range if lng_range > 0 else 0.5
    
    # Label
    v = "south" if lat_norm < 0.33 else ("north" if lat_norm > 0.67 else "central")
    h = "west" if lng_norm < 0.33 else ("east" if lng_norm > 0.67 else "central")
    
    if v == "central" and h == "central":
        return "center"
    if v == "central":
        return h
    if h == "central":
        return v
    return f"{v}-{h}"
