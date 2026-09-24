def extract_polygon_ring(polygon_like):
    """
    Accepts:
      - GeoJSON Feature
      - GeoJSON Polygon
      - GeoJSON MultiPolygon
      - raw coordinates [[[lng, lat], ...]]]
      - raw ring [[lng, lat], ...] or [(lng, lat), ...]
    Returns:
      list[[lng, lat], ...]
    """
    try:
        if not polygon_like:
            return None

        if isinstance(polygon_like, dict):
            geom = polygon_like.get("geometry") or polygon_like
            gtype = geom.get("type")
            coords = geom.get("coordinates")

            if gtype == "FeatureCollection":
                features = polygon_like.get("features") or []
                if not features:
                    return None
                return extract_polygon_ring(features[0])

            if gtype == "Polygon":
                coords = coords[0] if coords else None
            elif gtype == "MultiPolygon":
                coords = coords[0][0] if coords else None

            if coords and isinstance(coords, (list, tuple)):
                return [[float(pt[0]), float(pt[1])] for pt in coords if len(pt) >= 2]

        if isinstance(polygon_like, (list, tuple)):
            if not polygon_like:
                return None
            first = polygon_like[0]
            # Case 1: polygon coords [[[lng, lat], ...]] or [([(lng, lat), ...])]
            if isinstance(first, (list, tuple)) and len(first) > 0 and isinstance(first[0], (list, tuple)):
                if len(first[0]) >= 2 and isinstance(first[0][0], (int, float)):
                    return [[float(pt[0]), float(pt[1])] for pt in first if len(pt) >= 2]
                if isinstance(first[0][0], (list, tuple)):
                    return [[float(pt[0]), float(pt[1])] for pt in first[0] if len(pt) >= 2]
            # Case 2: raw ring [[lng, lat], ...] or [(lng, lat), ...]
            if isinstance(first, (list, tuple)) and len(first) >= 2 and isinstance(first[0], (int, float)):
                return [[float(pt[0]), float(pt[1])] for pt in polygon_like if len(pt) >= 2]

        return None
    except Exception:
        return None


def _build_affine_transform(bbox: list, W: int, H: int) -> tuple:
    """
    Build a validated GDAL GeoTransform 6-tuple from a bounding box.

    GDAL GeoTransform order:  (c, a, b, f, d, e)
      c  = x-coordinate of the upper-left corner of the upper-left pixel
      a  = pixel width (west–east resolution in map units)
      b  = row rotation (0 for north-up)
      f  = y-coordinate of the upper-left corner of the upper-left pixel
      d  = column rotation (0 for north-up)
      e  = pixel height (negative for north-up; south–north y-step)

    This is the canonical affine description used by GDAL and accepted by
    layer0_package_adapter.py._is_valid_transform().

    Parameters
    ----------
    bbox : [min_lon, min_lat, max_lon, max_lat]
    W    : raster width  (number of columns)
    H    : raster height (number of rows)

    Returns
    -------
    6-tuple of floats  (c, a, b, f, d, e)

    Raises
    ------
    ValueError  if bbox is invalid or W/H <= 0
    """
    if not bbox or len(bbox) < 4:
        raise ValueError(f"bbox must have 4 elements, got: {bbox!r}")
    min_lon, min_lat, max_lon, max_lat = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    if W <= 0 or H <= 0:
        raise ValueError(f"W and H must be positive, got W={W}, H={H}")

    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    if lon_span <= 0 or lat_span <= 0:
        raise ValueError(
            f"bbox has non-positive span: lon_span={lon_span}, lat_span={lat_span}"
        )

    a = lon_span / W   # pixel width  (positive, west→east)
    e = -(lat_span / H)  # pixel height (negative, north→south)
    c = min_lon        # x origin = left edge
    f = max_lat        # y origin = top  edge (north)
    b = 0.0            # no row rotation
    d = 0.0            # no column rotation

    return (c, a, b, f, d, e)
