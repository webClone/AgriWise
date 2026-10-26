"""
ASMAE Surface Generator (V82)
==============================

Generates ASMAE state and diagnostic surfaces for Layer 10 map visualization.
Enforces truthfulness-first UI gating, standard warning wordings, display trust tiers,
and blocks fake full-field broadcasts for state layers.
"""

from typing import List, Optional, Dict, Any, Tuple
import hashlib
import json
import math
import numpy as np

from services.agribrain.layer10_sire.schema import (
    Layer10Input, SurfaceArtifact, SurfaceType, PaletteId, GroundingClass,
    ASMAE_STATE_SURFACES, ASMAE_DIAGNOSTIC_SURFACES,
)
from services.agribrain.layer10_sire.adapters.l1_adapter import L1SpatialData
from services.agribrain.scientific_contracts import index_state_support_ledger
from services.agribrain.layer10_sire.surface_contract import resolve_surface_block_reasons


def _is_valid_direct_observation_count(val: Any) -> bool:
    """Validate that val is a finite, non-boolean, positive number representing count of direct observations."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    try:
        fval = float(val)
        return math.isfinite(fval) and fval > 0 and (isinstance(val, int) or fval.is_integer())
    except (TypeError, ValueError):
        return False


def _is_valid_finite_nonnegative(val: Any) -> bool:
    """Validate that val is a finite, non-boolean, nonnegative real number (preserving valid 0.0)."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    try:
        fval = float(val)
        return math.isfinite(fval) and fval >= 0.0
    except (TypeError, ValueError):
        return False


def _is_finite_real(val: Any) -> bool:
    """Return True if val is a finite real number (not None, bool, NaN, or Inf)."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    try:
        fval = float(val)
        return math.isfinite(fval)
    except (TypeError, ValueError):
        return False


def _parse_strict_bool(val: Any) -> bool:
    """Strictly parse booleans and scalar flags without converting invalid non-binary values to True."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val == 1
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return False
        return val == 1.0
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ("false", "0", "0.0", "no", "f", "n", "none", "null"):
            return False
        return s in ("true", "1", "yes", "t")
    return False


def _validate_covariance(cov: Any) -> Tuple[bool, bool]:
    """Validate covariance scalar, 1D diagonal vector, or 2D matrix.

    Returns:
        (is_valid, is_malformed)
        - If cov is None: (False, False)
        - If cov is invalid/malformed: (False, True)
        - If cov is valid: (True, False)
    """
    if cov is None:
        return False, False
    if isinstance(cov, bool):
        return False, True
    if isinstance(cov, (int, float)):
        if _is_valid_finite_nonnegative(cov):
            return True, False
        return False, True
    if isinstance(cov, (list, tuple)):
        if len(cov) == 0:
            return False, True
        any_nested = any(isinstance(x, (list, tuple)) for x in cov)
        all_nested = all(isinstance(x, (list, tuple)) for x in cov)
        if any_nested and not all_nested:
            return False, True
        if all_nested:
            n_rows = len(cov)
            if n_rows == 0:
                return False, True
            for row in cov:
                if not isinstance(row, (list, tuple)):
                    return False, True
                if len(row) == 0 or len(row) != n_rows:
                    return False, True
                for elem in row:
                    if isinstance(elem, bool) or not _is_finite_real(elem):
                        return False, True
            max_diag = max(float(cov[i][i]) for i in range(n_rows))
            max_elem = max(abs(float(cov[i][j])) for i in range(n_rows) for j in range(n_rows))
            scale = max(max_diag, max_elem)
            sym_tol = max(1e-14, 1e-4 * scale)

            for i in range(n_rows):
                if float(cov[i][i]) < 0.0:
                    return False, True
                for j in range(i + 1, n_rows):
                    diff = abs(float(cov[i][j]) - float(cov[j][i]))
                    pair_scale = max(abs(float(cov[i][j])), abs(float(cov[j][i])))
                    if diff > sym_tol or diff > max(1e-14, 1e-4 * pair_scale):
                        return False, True
            try:
                mat = np.array(cov, dtype=float)
                if not np.all(np.isfinite(mat)):
                    return False, True
                eigenvals = np.linalg.eigvalsh(mat)
                if not np.all(np.isfinite(eigenvals)):
                    return False, True
                max_eig = float(np.max(eigenvals)) if len(eigenvals) > 0 else 0.0
                mat_scale = max(max_diag, max_eig)
                if mat_scale <= 0.0:
                    if np.any(eigenvals < -1e-15):
                        return False, True
                else:
                    tol = max(1e-15, 1e-6 * mat_scale)
                    if np.any(eigenvals < -tol):
                        return False, True
            except Exception:
                return False, True
            return True, False
        else:
            if len(cov) == 0:
                return False, True
            for elem in cov:
                if isinstance(elem, bool) or not _is_finite_real(elem):
                    return False, True
                if float(elem) < 0.0:
                    return False, True
            return True, False
    return False, True


def _are_covariances_equivalent(c1: Any, c2: Any) -> bool:
    """Check if two valid covariance structures represent the same covariance within numerical tolerance."""
    try:
        arr1 = np.array(c1, dtype=float)
        arr2 = np.array(c2, dtype=float)
        if arr1.shape == arr2.shape:
            return bool(np.all(np.abs(arr1 - arr2) <= 1e-4))
        if arr1.size == 1 and arr2.size == 1:
            return bool(abs(arr1.item() - arr2.item()) <= 1e-4)
        return False
    except Exception:
        return False


def _is_variance_compatible_with_covariance(resolved_var: float, cov: Any) -> bool:
    """Check if a scalar variance is compatible with the supplied covariance structure."""
    try:
        arr = np.array(cov, dtype=float)
        if arr.size == 1:
            return bool(abs(arr.item() - resolved_var) <= 1e-4)
        if arr.ndim == 1:
            return bool(abs(arr[0] - resolved_var) <= 1e-4)
        if arr.ndim == 2:
            return bool(abs(arr[0, 0] - resolved_var) <= 1e-4)
        return False
    except Exception:
        return False


def _safe_square(val: float) -> Optional[float]:
    """Square a float safely, returning finite float or None on overflow/nonfinite."""
    try:
        sq = val ** 2
        if not math.isfinite(sq):
            return None
        return sq
    except (OverflowError, ArithmeticError, ValueError):
        return None


def _validate_prior_distribution(dist: Any) -> Tuple[bool, bool]:
    """Validate an alternate prior_distribution.

    Returns:
        (has_valid_distribution, is_malformed)
        - If dist is None: (False, False)
        - If dist is invalid/malformed or incomplete: (False, True)
        - If dist is a valid distribution: (True, False)
    """
    if dist is None:
        return False, False
    if not isinstance(dist, dict):
        return False, True
    if not dist:
        return False, True

    # Validate family / distribution keys if present
    if "family" in dist:
        fam = dist["family"]
        if not isinstance(fam, str) or not fam.strip():
            return False, True
    if "distribution" in dist:
        dval = dist["distribution"]
        if not isinstance(dval, str) or not dval.strip():
            return False, True
    if "family" in dist and "distribution" in dist:
        if dist["family"].strip().lower() != dist["distribution"].strip().lower():
            return False, True

    # Validate mean / mu
    has_mean = "mean" in dist
    has_mu = "mu" in dist
    if has_mean and not _is_finite_real(dist["mean"]):
        return False, True
    if has_mu and not _is_finite_real(dist["mu"]):
        return False, True
    if has_mean and has_mu:
        if abs(float(dist["mean"]) - float(dist["mu"])) > 1e-4:
            return False, True

    # Validate variance / var
    has_variance = "variance" in dist
    has_var = "var" in dist
    if has_variance and not _is_valid_finite_nonnegative(dist["variance"]):
        return False, True
    if has_var and not _is_valid_finite_nonnegative(dist["var"]):
        return False, True
    if has_variance and has_var:
        if abs(float(dist["variance"]) - float(dist["var"])) > 1e-4:
            return False, True

    # Validate std / sigma
    has_std = "std" in dist
    has_sigma = "sigma" in dist
    if has_std and not _is_valid_finite_nonnegative(dist["std"]):
        return False, True
    if has_sigma and not _is_valid_finite_nonnegative(dist["sigma"]):
        return False, True
    if has_std and has_sigma:
        if abs(float(dist["std"]) - float(dist["sigma"])) > 1e-4:
            return False, True

    # Cross-validate variance and std if both supplied
    resolved_var: Optional[float] = None
    if has_variance:
        resolved_var = float(dist["variance"])
    elif has_var:
        resolved_var = float(dist["var"])

    resolved_std: Optional[float] = None
    if has_std:
        resolved_std = float(dist["std"])
    elif has_sigma:
        resolved_std = float(dist["sigma"])

    if resolved_std is not None:
        sq_std = _safe_square(resolved_std)
        if sq_std is None:
            return False, True
        if resolved_var is not None:
            if abs(sq_std - resolved_var) > 1e-4:
                return False, True
        else:
            resolved_var = sq_std

    # Validate covariance / cov
    has_cov = "covariance" in dist
    has_cov_alias = "cov" in dist
    has_valid_cov = False

    if has_cov:
        c_valid, c_malformed = _validate_covariance(dist["covariance"])
        if c_malformed or not c_valid:
            return False, True
        has_valid_cov = True

    if has_cov_alias:
        c_valid, c_malformed = _validate_covariance(dist["cov"])
        if c_malformed or not c_valid:
            return False, True
        has_valid_cov = True

    # Cross-validate covariance aliases if both declared
    if has_cov and has_cov_alias:
        if not _are_covariances_equivalent(dist["covariance"], dist["cov"]):
            return False, True

    # Cross-validate scalar variance against covariance if both declared
    if resolved_var is not None:
        if has_cov:
            if not _is_variance_compatible_with_covariance(resolved_var, dist["covariance"]):
                return False, True
        if has_cov_alias:
            if not _is_variance_compatible_with_covariance(resolved_var, dist["cov"]):
                return False, True

    # Prior evidence requires an explicit, valid dispersion parameter
    has_dispersion = (resolved_var is not None) or (resolved_std is not None) or has_valid_cov
    if not has_dispersion:
        return False, True

    return True, False


RECOGNIZED_SPATIAL_SUPPORTS = {
    "microzone_grid",
    "raster",
    "pixel_native",
    "sub_grid",
    "plot",
    "zone",
    "regional",
    "plot_level_only",
}


def _validate_spatial_support(spatial: Any) -> Tuple[bool, bool]:
    """Validate spatial_support token.

    Returns:
        (has_valid_spatial, is_malformed)
        - If spatial is empty, None, 'none', 'unsupported': (False, False)
        - If spatial is a recognized spatial support: (True, False)
        - If spatial is an arbitrary/unknown string (e.g. 'not-a-raster'): (False, True)
    """
    if spatial is None:
        return False, False
    s_str = str(spatial).strip().lower()
    if s_str in ("", "none", "unsupported"):
        return False, False
    if s_str in RECOGNIZED_SPATIAL_SUPPORTS:
        return True, False
    return False, True


def _is_surface_revoked_or_unsupported(s: Any) -> Tuple[bool, Optional[str]]:
    """Determine if an ingredient surface is unsupported or revoked by status or block reasons."""
    if s is None:
        return True, "surface_missing"
    sprov = getattr(s, "provenance", {}) or {}
    sup_class = sprov.get("support_class")
    ev_class = sprov.get("evidence_class")
    if sup_class == "unsupported" or ev_class == "Unsupported":
        return True, "ingredient_unsupported"

    raw_blocks = resolve_surface_block_reasons(
        getattr(s, "block_reasons", None),
        sprov,
    )

    REVOCATION_BLOCK_STRINGS = (
        "local_support_revoked",
        "support_revoked",
        "evidence_revoked",
        "blocked",
        "revoked",
    )
    for r in raw_blocks:
        r_str = str(r).lower()
        if any(rev in r_str for rev in REVOCATION_BLOCK_STRINGS):
            return True, "ingredient_blocked"

    raw_status = str(sprov.get("support_status") or "").lower()
    if raw_status in ("unsupported", "revoked", "blocked", "failed", "none"):
        return True, "ingredient_unsupported"

    return False, None


_ASMAE_NEAREST_RESAMPLE_TYPES = {
    SurfaceType.ASMAE_EXPORT_ELIGIBILITY,
    SurfaceType.ASMAE_1M_ADVISORY_MASK,
    SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK,
    SurfaceType.ASMAE_5M_GENERALIZED_MASK,
}


def _plain_grid_spec(value: Any) -> Optional[Dict[str, Any]]:
    """Return a JSON-safe grid specification without guessing its convention."""
    if value is None:
        return None
    if isinstance(value, dict):
        raw = dict(value)
    elif callable(getattr(value, "to_dict", None)):
        raw = dict(value.to_dict())
    else:
        raw = {
            key: getattr(value, key, None)
            for key in (
                "crs", "transform", "bounds", "width", "height",
                "resolution", "resolution_m", "nodata", "grid_hash",
                "transform_convention",
            )
            if getattr(value, key, None) is not None
        }
    if not raw:
        return None
    for key in ("transform", "bounds"):
        if raw.get(key) is not None:
            raw[key] = [float(v) for v in raw[key]]
    for key in ("width", "height"):
        if raw.get(key) is not None:
            raw[key] = int(raw[key])
    if raw.get("crs") is not None:
        raw["crs"] = str(raw["crs"])
    return raw


def _rectangular_grid(grid: Any) -> Tuple[List[List[Optional[float]]], int, int]:
    """Normalize only the container type; never reshape or transpose values."""
    if isinstance(grid, np.ndarray):
        if grid.ndim != 2:
            raise ValueError("ASMAE_GRID_NOT_2D")
        rows = grid.tolist()
    elif isinstance(grid, (list, tuple)):
        rows = list(grid)
    else:
        raise ValueError("ASMAE_GRID_NOT_2D")
    if not rows or not all(isinstance(row, (list, tuple)) for row in rows):
        raise ValueError("ASMAE_GRID_NOT_2D")
    width = len(rows[0])
    if width <= 0 or any(len(row) != width for row in rows):
        raise ValueError("ASMAE_GRID_RAGGED")
    return [list(row) for row in rows], len(rows), width


def _validated_north_up_gdal_spec(
    value: Any,
    *,
    height: int,
    width: int,
    label: str,
) -> Dict[str, Any]:
    """Prove the Layer-1 GDAL affine convention against bounds and dimensions."""
    spec = _plain_grid_spec(value)
    if not spec:
        raise ValueError(f"ASMAE_GRID_ALIGNMENT_UNPROVEN:{label}_grid_spec_missing")
    try:
        spec_h = int(spec["height"])
        spec_w = int(spec["width"])
        bounds = [float(v) for v in spec["bounds"]]
        transform = [float(v) for v in spec["transform"]]
        crs = str(spec["crs"] or "").strip()
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"ASMAE_GRID_ALIGNMENT_UNPROVEN:{label}_grid_spec_incomplete"
        ) from exc
    if spec_h != int(height) or spec_w != int(width):
        raise ValueError(f"ASMAE_GRID_ALIGNMENT_UNPROVEN:{label}_dimension_mismatch")
    if len(bounds) != 4 or len(transform) != 6:
        raise ValueError(f"ASMAE_GRID_ALIGNMENT_UNPROVEN:{label}_geometry_invalid")
    if not crs or not all(np.isfinite(v) for v in bounds + transform):
        raise ValueError(f"ASMAE_GRID_ALIGNMENT_UNPROVEN:{label}_geometry_invalid")

    min_x, min_y, max_x, max_y = bounds
    x0, dx, rx, y0, ry, dy = transform
    if max_x <= min_x or max_y <= min_y or dx <= 0.0 or dy >= 0.0:
        raise ValueError(f"ASMAE_GRID_ALIGNMENT_UNPROVEN:{label}_not_north_up")
    tolerance = max(max_x - min_x, max_y - min_y, 1.0) * 1e-8
    if (
        abs(rx) > tolerance
        or abs(ry) > tolerance
        or abs(x0 - min_x) > tolerance
        or abs(y0 - max_y) > tolerance
        or abs((x0 + dx * width) - max_x) > tolerance
        or abs((y0 + dy * height) - min_y) > tolerance
    ):
        raise ValueError(
            f"ASMAE_GRID_ALIGNMENT_UNPROVEN:{label}_gdal_bounds_mismatch"
        )
    spec["width"] = int(width)
    spec["height"] = int(height)
    spec["bounds"] = bounds
    spec["transform"] = transform
    spec["crs"] = crs
    spec["transform_convention"] = "gdal"
    return spec


def _grid_identity(spec: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _source_grid_spec_for_surface(
    metadata: Dict[str, Any],
    fallback: Any,
) -> Any:
    """Prefer the exact RasterRef grid bound to this numeric surface."""
    explicit = metadata.get("source_grid_spec") or metadata.get("grid_spec")
    if explicit is not None:
        return explicit
    geometry_keys = ("crs", "bounds", "transform", "width", "height")
    if any(metadata.get(key) is not None for key in geometry_keys):
        return {
            key: metadata.get(key)
            for key in (
                *geometry_keys,
                "resolution", "resolution_m", "nodata", "grid_hash",
                "transform_convention",
            )
            if metadata.get(key) is not None
        }
    return fallback


def _record_alignment_failure(
    l1_data: L1SpatialData,
    *,
    surface_type: SurfaceType,
    variable: str,
    reason: str,
) -> None:
    """Expose a typed failure on the adapted Layer-1 boundary value."""
    failure = {
        "component": "ASMAE_SURFACE_ALIGNMENT",
        "code": "ASMAE_GRID_ALIGNMENT_FAILED",
        "surface_type": surface_type.value,
        "variable": variable,
        "reason": reason,
    }
    failures = getattr(l1_data, "asmae_alignment_failures", None)
    if not isinstance(failures, list):
        failures = []
        l1_data.asmae_alignment_failures = failures
    if failure not in failures:
        failures.append(failure)

    if not isinstance(getattr(l1_data, "asmae_feature_pack", None), dict):
        l1_data.asmae_feature_pack = {}
    feature_failures = l1_data.asmae_feature_pack.setdefault(
        "surface_alignment_failures", []
    )
    if isinstance(feature_failures, list) and failure not in feature_failures:
        feature_failures.append(dict(failure))


def _align_asmae_grid_to_target(
    grid: Any,
    *,
    source_grid_spec: Any,
    target_grid_spec: Any,
    target_height: int,
    target_width: int,
    method: str,
) -> Tuple[List[List[Optional[float]]], Optional[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, Any]]:
    """Align one ASMAE raster using proven CRS/affine geometry only."""
    rows, source_height, source_width = _rectangular_grid(grid)
    source_raw = _plain_grid_spec(source_grid_spec)
    target_raw = _plain_grid_spec(target_grid_spec)
    if method not in {"nearest", "bilinear"}:
        raise ValueError(f"ASMAE_GRID_ALIGNMENT_UNPROVEN:unsupported_method:{method}")

    # Shape equality is not geographic identity. Both contracts must be
    # complete and affine-valid even when the arrays happen to have the same
    # dimensions.
    source = _validated_north_up_gdal_spec(
        source_raw, height=source_height, width=source_width, label="source"
    )
    target = _validated_north_up_gdal_spec(
        target_raw, height=target_height, width=target_width, label="target"
    )
    def _clean_row_values(grid_rows: List[List[Optional[float]]], nodata_val: Any) -> List[List[Optional[float]]]:
        cleaned = []
        for r in grid_rows:
            cleaned_row = []
            for v in r:
                if v is None:
                    cleaned_row.append(None)
                else:
                    try:
                        fv = float(v)
                        if not np.isfinite(fv):
                            cleaned_row.append(None)
                        elif nodata_val is not None and np.isclose(fv, float(nodata_val), rtol=0.0, atol=1e-6):
                            cleaned_row.append(None)
                        elif np.isclose(fv, -9999.0, rtol=0.0, atol=1e-6):
                            cleaned_row.append(None)
                        else:
                            cleaned_row.append(fv)
                    except (ValueError, TypeError, OverflowError):
                        cleaned_row.append(None)
            cleaned.append(cleaned_row)
        return cleaned

    same_crs = source["crs"].upper() == target["crs"].upper()
    if (
        (source_height, source_width) == (target_height, target_width)
        and same_crs
        and np.allclose(source["transform"], target["transform"], rtol=0.0, atol=1e-12)
    ):
        return _clean_row_values(rows, source.get("nodata")), source, target, {
            "display_resampled": False,
            "reprojection_applied": False,
            "resampling_method": "identity_grid",
            "source_grid_shape": [source_height, source_width],
            "display_grid_shape": [target_height, target_width],
            "source_grid_identity": _grid_identity(source),
            "display_grid_identity": _grid_identity(target),
            "source_crs": source["crs"],
            "display_crs": target["crs"],
        }

    src = np.asarray(rows, dtype=np.float64)
    nodata = source.get("nodata")
    if nodata is not None:
        try:
            src[np.isclose(src, float(nodata), rtol=0.0, atol=0.0)] = np.nan
        except (TypeError, ValueError, OverflowError):
            pass

    if not same_crs:
        # Cross-CRS display alignment is a real reprojection. Rasterio/GDAL is
        # a production dependency; if it or either CRS is unavailable, fail
        # closed rather than falling back to row/column sampling.
        try:
            from rasterio.crs import CRS
            from rasterio.enums import Resampling
            from rasterio.transform import Affine
            from rasterio.warp import reproject

            src_crs = CRS.from_user_input(source["crs"])
            dst_crs = CRS.from_user_input(target["crs"])
            destination = np.full(
                (target_height, target_width), np.nan, dtype=np.float64
            )
            reproject(
                source=src,
                destination=destination,
                src_transform=Affine.from_gdal(*source["transform"]),
                src_crs=src_crs,
                src_nodata=np.nan,
                dst_transform=Affine.from_gdal(*target["transform"]),
                dst_crs=dst_crs,
                dst_nodata=np.nan,
                resampling=(
                    Resampling.nearest
                    if method == "nearest"
                    else Resampling.bilinear
                ),
                init_dest_nodata=True,
            )
        except (ImportError, ModuleNotFoundError) as exc:
            raise ValueError(
                "ASMAE_GRID_ALIGNMENT_UNPROVEN:reprojection_dependency_missing"
            ) from exc
        except Exception as exc:
            raise ValueError(
                "ASMAE_GRID_ALIGNMENT_UNPROVEN:reprojection_failed"
            ) from exc

        if not np.isfinite(destination).any():
            raise ValueError(
                "ASMAE_GRID_ALIGNMENT_UNPROVEN:reprojection_no_overlap_or_valid_pixels"
            )
        reprojected = [
            [float(value) if np.isfinite(value) else None for value in row]
            for row in destination
        ]
        return reprojected, source, target, {
            "display_resampled": True,
            "reprojection_applied": True,
            "resampling_method": method,
            "source_grid_shape": [source_height, source_width],
            "display_grid_shape": [target_height, target_width],
            "source_grid_identity": _grid_identity(source),
            "display_grid_identity": _grid_identity(target),
            "source_transform_convention": "gdal",
            "display_transform_convention": "gdal",
            "source_crs": source["crs"],
            "display_crs": target["crs"],
        }

    result: List[List[Optional[float]]] = [
        [None for _ in range(target_width)] for _ in range(target_height)
    ]
    src_min_x, src_min_y, src_max_x, src_max_y = source["bounds"]
    src_x0, src_dx, _, src_y0, _, src_dy = source["transform"]
    tgt_x0, tgt_dx, _, tgt_y0, _, tgt_dy = target["transform"]

    for row in range(target_height):
        y = tgt_y0 + (row + 0.5) * tgt_dy
        if y < src_min_y or y > src_max_y:
            continue
        source_row = (src_y0 - y) / abs(src_dy) - 0.5
        for col in range(target_width):
            x = tgt_x0 + (col + 0.5) * tgt_dx
            if x < src_min_x or x > src_max_x:
                continue
            source_col = (x - src_x0) / src_dx - 0.5
            if method == "nearest":
                sr = int(np.floor(source_row + 0.5))
                sc = int(np.floor(source_col + 0.5))
                if 0 <= sr < source_height and 0 <= sc < source_width:
                    value = src[sr, sc]
                    if np.isfinite(value):
                        result[row][col] = float(value)
                continue

            r0 = int(np.floor(source_row))
            c0 = int(np.floor(source_col))
            dr = source_row - r0
            dc = source_col - c0
            weighted = 0.0
            weight_sum = 0.0
            for sr, rw in ((r0, 1.0 - dr), (r0 + 1, dr)):
                for sc, cw in ((c0, 1.0 - dc), (c0 + 1, dc)):
                    weight = rw * cw
                    if weight <= 0.0 or not (0 <= sr < source_height and 0 <= sc < source_width):
                        continue
                    value = src[sr, sc]
                    if np.isfinite(value):
                        weighted += float(value) * weight
                        weight_sum += weight
            if weight_sum > 0.0:
                result[row][col] = weighted / weight_sum

    return result, source, target, {
        "display_resampled": True,
        "reprojection_applied": False,
        "resampling_method": method,
        "source_grid_shape": [source_height, source_width],
        "display_grid_shape": [target_height, target_width],
        "source_grid_identity": _grid_identity(source),
        "display_grid_identity": _grid_identity(target),
        "source_transform_convention": "gdal",
        "display_transform_convention": "gdal",
        "source_crs": source["crs"],
        "display_crs": target["crs"],
    }


align_asmae_grid_to_target = _align_asmae_grid_to_target


def get_standard_variable_name(stype: SurfaceType, meta_var: Optional[str] = None) -> str:
    from services.agribrain.scientific_contracts.state_schema_ref import canonical_state_key, STATE_ORDER
    v = (meta_var or "").strip().lower()
    s = getattr(stype, "value", str(stype))

    canon_v = canonical_state_key(v) if v else None
    canon_s = canonical_state_key(s)

    # Reject conflicting canonical declarations
    if canon_v and canon_v in STATE_ORDER and canon_s and canon_s in STATE_ORDER and canon_v != canon_s:
        return "conflict_rejected"

    # If meta_var is already an exact canonical state in STATE_ORDER, prefer it
    if canon_v and canon_v in STATE_ORDER:
        return canon_v

    # Resolve from surface type
    if canon_s and canon_s in STATE_ORDER:
        return canon_s

    # Specific water distinctions before generic water
    s_low = s.lower()
    if "root_zone_water" in v or "root_zone_water" in s_low or "rootzone" in v or "rootzone" in s_low:
        return "root_zone_water"
    if "surface_wetness" in v or "surface_wetness" in s_low or "wetness" in v or "wetness" in s_low:
        return "surface_wetness_event"
    if "canopy_water" in v or "canopy_water" in s_low:
        return "canopy_water"
    if "water" in v or "water" in s_low:
        return "canopy_water"

    if "vigor" in v or "vigor" in s or "ndvi" in v or "ndvi" in s:
        return "vigor"
    if "salinity" in v or "salinity" in s:
        return "salinity_stress"
    if "biotic" in v or "biotic" in s or "confounder" in v or "confounder" in s:
        return "biotic_confounder"
    return v or s


def get_surface_display_policy(
    confidence: float,
    uncertainty: float,
    resolution_m: float,
    bma_status: Optional[str],
    cross_layer_conflict: float,
    is_certified_v90: bool = False,
) -> Dict[str, Any]:
    """Determine UI display trust tier, desaturation level, alpha, and warning codes."""
    warning_codes = []

    conf_valid = isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and math.isfinite(confidence)
    unc_valid = isinstance(uncertainty, (int, float)) and not isinstance(uncertainty, bool) and math.isfinite(uncertainty)
    clc_valid = isinstance(cross_layer_conflict, (int, float)) and not isinstance(cross_layer_conflict, bool) and math.isfinite(cross_layer_conflict)

    if resolution_m <= 1.0 and not is_certified_v90:
        warning_codes.append("resolution_1m_blocked")

    if not clc_valid or cross_layer_conflict > 0.45:
        warning_codes.append("cross_layer_conflict")

    if not conf_valid or confidence < 0.60:
        warning_codes.append("low_confidence")

    if not unc_valid or uncertainty > 0.40:
        warning_codes.append("high_uncertainty")

    if bma_status != "success":
        warning_codes.append("bma_not_success")

    # If no major warnings, check for mild warnings for provisional tier
    if not warning_codes:
        if (conf_valid and 0.60 <= confidence <= 0.80) or (unc_valid and 0.30 <= uncertainty <= 0.40):
            warning_codes.append("mild_warning")

    # Determine display trust tier based on the highest severity warning
    if "resolution_1m_blocked" in warning_codes:
        tier = "visual_only"
        desat = 0.8
        alpha = 0.8
    elif "cross_layer_conflict" in warning_codes:
        tier = "conflict"
        desat = 0.5
        alpha = 0.9
    elif "low_confidence" in warning_codes or "high_uncertainty" in warning_codes:
        tier = "diagnostic"
        desat = 1.0
        alpha = 0.7
    elif "bma_not_success" in warning_codes:
        tier = "diagnostic"
        desat = 0.8
        alpha = 0.8
    elif "mild_warning" in warning_codes:
        tier = "provisional"
        desat = 0.3
        alpha = 1.0
    else:
        tier = "trusted"
        desat = 0.0
        alpha = 1.0

    requires_warning = len(warning_codes) > 0

    return {
        "display_trust_tier": tier,
        "desaturation_level": desat,
        "alpha_multiplier": alpha,
        "requires_user_warning": requires_warning,
        "warning_codes": warning_codes,
    }


def compute_asmae_support_classification(
    *,
    real_ev: bool,
    source_reality: str,
    meta: Dict[str, Any],
    stype: SurfaceType,
    state_support_ledger: Optional[Dict[str, Any]] = None,
    feature_name: Optional[str] = None,
) -> Dict[str, Any]:
    valid_classes = {
        "directly_assimilated",
        "proxy_assimilated",
        "indirectly_constrained",
        "prior_constrained",
        "unsupported",
        "derived_diagnostic",
    }

    derived_diagnostic_types = set(ASMAE_DIAGNOSTIC_SURFACES) | {
        SurfaceType.ASMAE_CONFIDENCE,
        getattr(SurfaceType, "CONFIDENCE_ASMAE", None),
    }

    # Diagnostics describe the inference process; a real upstream raster does
    # not turn resolution, uncertainty, agreement, or support into an observed
    # biophysical state.
    if stype in derived_diagnostic_types:
        return {
            "support_class": "derived_diagnostic",
            "evidence_class": "Derived diagnostic",
            "direct_observation": False,
            "scouting_zone_eligible": True,
            "management_zone_eligible": False,
            "zone_statistics_eligible": False,
        }

    support_class = None
    state_entry = None
    if state_support_ledger and feature_name:
        from services.agribrain.scientific_contracts.state_schema_ref import canonical_state_key
        canon_feature = canonical_state_key(feature_name)
        state_entry = (
            state_support_ledger.get(canon_feature)
            or state_support_ledger.get(feature_name)
            or state_support_ledger.get(f"asmae_{canon_feature}")
        )
        if state_entry:
            raw_status = (
                state_entry.get("support_status")
                if isinstance(state_entry, dict)
                else getattr(state_entry, "support_status", None)
            )
            if hasattr(raw_status, "value"):
                raw_status = raw_status.value
            raw_status_str = str(raw_status or "").lower()

            raw_rel = (
                state_entry.get("observation_relationship")
                if isinstance(state_entry, dict)
                else getattr(state_entry, "observation_relationship", None)
            )
            if hasattr(raw_rel, "value"):
                raw_rel = raw_rel.value
            rel_str = str(raw_rel or "").lower()

            raw_blocks = (
                state_entry.get("block_reasons")
                if isinstance(state_entry, dict)
                else getattr(state_entry, "block_reasons", ())
            ) or ()
            has_revocation_blocks = any(
                r in ("local_support_revoked", "support_revoked", "evidence_revoked", "blocked")
                for r in raw_blocks
            )

            # S12-02: Denial, revocation, and block reasons take strict precedence
            if raw_status_str in ("unsupported", "blocked", "failed", "revoked", "none") or rel_str == "unsupported" or has_revocation_blocks:
                support_class = "unsupported"
            elif raw_status_str == "prior_constrained":
                # S12-04 / S673-03: Strict actual-prior qualification
                raw_var = (
                    state_entry.get("prior_variance")
                    if isinstance(state_entry, dict)
                    else getattr(state_entry, "prior_variance", None)
                )
                has_valid_var = _is_valid_finite_nonnegative(raw_var)
                has_actual_prior_flag = (
                    (state_entry.get("has_actual_prior") is True or state_entry.get("has_prior_evidence") is True)
                    if isinstance(state_entry, dict)
                    else (getattr(state_entry, "has_actual_prior", None) is True or getattr(state_entry, "has_prior_evidence", None) is True)
                )
                raw_dist = (
                    state_entry.get("prior_distribution")
                    if isinstance(state_entry, dict)
                    else getattr(state_entry, "prior_distribution", None)
                )
                has_valid_dist, is_dist_malformed = _validate_prior_distribution(raw_dist)

                raw_spatial = (
                    state_entry.get("spatial_support")
                    if isinstance(state_entry, dict)
                    else getattr(state_entry, "spatial_support", None)
                )
                has_valid_spatial, is_spatial_malformed = _validate_spatial_support(raw_spatial)

                has_invalid_alternate_proof = is_dist_malformed or is_spatial_malformed

                is_explicitly_denied = (
                    (state_entry.get("has_actual_prior") is False or state_entry.get("has_prior_evidence") is False)
                    if isinstance(state_entry, dict)
                    else (getattr(state_entry, "has_actual_prior", None) is False or getattr(state_entry, "has_prior_evidence", None) is False)
                ) or (raw_var is not None and not has_valid_var) or has_invalid_alternate_proof

                if not is_explicitly_denied and (has_valid_var or has_actual_prior_flag or has_valid_dist or has_valid_spatial):
                    support_class = "prior_constrained"
                else:
                    support_class = "unsupported"
            elif raw_status_str in valid_classes:
                support_class = raw_status_str
            else:
                try:
                    from services.agribrain.scientific_contracts.state_support import resolve_state_evidence_class
                    ev_class = resolve_state_evidence_class(state_entry)
                    support_class = ev_class.value
                except Exception:
                    pass

            # S12-05: Direct observation status strictly requires verified direct measurement proof
            if support_class == "directly_assimilated":
                raw_direct = (
                    state_entry.get("direct_observation_count")
                    if isinstance(state_entry, dict)
                    else getattr(state_entry, "direct_observation_count", None)
                )
                has_valid_direct = _is_valid_direct_observation_count(raw_direct)
                if not has_valid_direct and rel_str not in ("direct", "direct_observation"):
                    support_class = "indirectly_constrained" if rel_str == "indirect" else "proxy_assimilated"

    if not support_class:
        raw_class = meta.get("support_class") or meta.get("evidence_support_class")
        raw_var = meta.get("prior_variance")
        has_valid_var = _is_valid_finite_nonnegative(raw_var)
        has_actual_prior_flag = (
            meta.get("has_actual_prior") is True
            or meta.get("has_prior_evidence") is True
            or meta.get("has_enkf_prior") is True
        )
        raw_dist = meta.get("prior_distribution")
        has_valid_dist, is_dist_malformed = _validate_prior_distribution(raw_dist)

        raw_spatial = meta.get("spatial_support")
        has_valid_spatial, is_spatial_malformed = _validate_spatial_support(raw_spatial)

        is_prior_denied = (
            meta.get("has_actual_prior") is False
            or meta.get("has_prior_evidence") is False
            or (raw_var is not None and not has_valid_var)
            or is_dist_malformed
            or is_spatial_malformed
        )

        if raw_class == "directly_assimilated":
            raw_direct = meta.get("direct_observation_count")
            has_valid_direct = _is_valid_direct_observation_count(raw_direct)
            has_direct_flag = meta.get("direct_observation") is True
            if has_valid_direct or has_direct_flag:
                support_class = "directly_assimilated"
            else:
                support_class = "indirectly_constrained"
        elif raw_class in ("proxy_assimilated", "indirectly_constrained"):
            support_class = raw_class
        elif raw_class == "prior_constrained":
            if not is_prior_denied and (has_valid_var or has_actual_prior_flag or has_valid_dist or has_valid_spatial):
                support_class = "prior_constrained"
            else:
                support_class = "unsupported"
        elif not is_prior_denied and (has_valid_var or has_actual_prior_flag or has_valid_dist or has_valid_spatial or meta.get("has_enkf_proxy_fallback") is True):
            support_class = "prior_constrained"
        else:
            support_class = "unsupported"

    from services.agribrain.layer05_asmae.state.descriptors import (
        STATE_DESCRIPTOR_BY_NAME,
        AuthorityCeiling,
    )
    from services.agribrain.scientific_contracts.state_schema_ref import canonical_state_key
    canon_name = canonical_state_key(feature_name or stype.value)
    descriptor = STATE_DESCRIPTOR_BY_NAME.get(canon_name)
    descriptor_is_prescription = (
        descriptor is not None
        and descriptor.authority_ceiling == AuthorityCeiling.PRESCRIPTION_ELIGIBLE
    )

    from services.agribrain.layer10_sire.surface_contract import _normalize_ceiling_token, resolve_surface_block_reasons

    # AB-R03: Three-way authority ceiling intersection (descriptor x ledger x metadata)
    CEILING_RANKS = {
        "VISUALIZATION": 0,
        "MONITORING_ONLY": 1,
        "DIAGNOSTIC": 2,
        "TRAINING_EXPORT": 3,
        "STATE_UPDATE": 4,
        "PRESCRIPTION_DRIVER": 5,
        "PRESCRIPTION_ELIGIBLE": 5,
        "MANAGED_PRESCRIPTION": 5,
        "FIELD_PRESCRIPTION": 5,
        "FULL_SYSTEM_AUTONOMOUS": 5,
    }
    RANK_TO_CANONICAL = {
        0: "VISUALIZATION",
        1: "MONITORING_ONLY",
        2: "DIAGNOSTIC",
        3: "TRAINING_EXPORT",
        4: "STATE_UPDATE",
        5: "PRESCRIPTION_DRIVER",
    }

    raw_ceilings = []
    if descriptor and descriptor.authority_ceiling is not None:
        raw_ceilings.append(descriptor.authority_ceiling)
    if state_entry:
        if isinstance(state_entry, dict):
            c = state_entry.get("authority_ceiling") or state_entry.get("authorityCeiling") or state_entry.get("authority")
        else:
            c = getattr(state_entry, "authority_ceiling", None)
        if c is not None:
            raw_ceilings.append(c)
    if meta:
        c = meta.get("authority_ceiling") or meta.get("authorityCeiling") or meta.get("authority")
        if c is not None:
            raw_ceilings.append(c)

    normalized_ceilings = [
        _normalize_ceiling_token(c) for c in raw_ceilings if c is not None and str(c).strip()
    ]
    if normalized_ceilings:
        # Unknown ceiling tokens fail closed to rank 0 (VISUALIZATION)
        min_rank = min(CEILING_RANKS.get(tok, 0) for tok in normalized_ceilings)
        state_ceiling = RANK_TO_CANONICAL.get(min_rank, "DIAGNOSTIC")
    else:
        min_rank = 2
        state_ceiling = "DIAGNOSTIC"

    state_block_reasons = resolve_surface_block_reasons(state_entry, meta)
    has_blocking_reasons = bool(state_block_reasons)

    is_management_eligible = (
        descriptor_is_prescription
        and min_rank >= 5
        and not has_blocking_reasons
    )

    if support_class == "directly_assimilated":
        evidence_class = "Observed"
        direct_observation = True
        scouting = True
        mgmt = is_management_eligible
        stats = True
    elif support_class == "proxy_assimilated":
        evidence_class = "Proxy-Assimilated"
        direct_observation = False
        scouting = True
        mgmt = False  # Proxy states support scouting, not management/prescription authority
        stats = True
    elif support_class == "indirectly_constrained":
        evidence_class = "Indirectly-Constrained"
        direct_observation = False
        scouting = True
        mgmt = False
        stats = True
    elif support_class == "prior_constrained":
        evidence_class = "Prior-Constrained"
        direct_observation = False
        scouting = True
        mgmt = False
        stats = False
    else:
        support_class = "unsupported"
        evidence_class = "Unsupported"
        direct_observation = False
        scouting = False
        mgmt = False
        stats = False

    is_alias = stype in (
        SurfaceType.ASMAE_POSTERIOR_CONCENTRATION,
        SurfaceType.ASMAE_CONFIDENCE,
        getattr(SurfaceType, "CONFIDENCE_ASMAE", None),
    )
    if is_alias:
        stats = False

    return {
        "support_class": support_class,
        "evidence_class": evidence_class,
        "direct_observation": direct_observation,
        "scouting_zone_eligible": scouting,
        "management_zone_eligible": mgmt,
        "zone_statistics_eligible": stats,
        "block_reasons": list(state_block_reasons) if state_block_reasons else [],
        "authority_ceiling": state_ceiling,
    }


def generate_asmae_surfaces(
    inp: Layer10Input,
    H: int,
    W: int,
    l1_data: Optional[L1SpatialData] = None,
) -> List[SurfaceArtifact]:
    """Generate all registered ASMAE state and diagnostic surfaces."""
    from rollout.rollout_policy import should_render_l10_asmae
    if not should_render_l10_asmae(inp.plot_id):
        return []

    if l1_data is None:
        from services.agribrain.layer10_sire.adapters.l1_adapter import adapt_l1
        l1_data = adapt_l1(inp.field_tensor, H, W)

    # P0-1 Check if any ASMAE input exists in raster_maps, raster_metadata, or last_values
    has_asmae_input = any(
        str(k).lower().startswith("asmae_")
        for k in (
            list(l1_data.raster_maps.keys())
            + list(l1_data.raster_metadata.keys())
            + list(l1_data.last_values.keys())
        )
    )

    if not has_asmae_input:
        return []

    surfaces = []
    evidence_state = dict(getattr(l1_data, "asmae_evidence_state", {}) or {})
    feature_pack = dict(getattr(l1_data, "asmae_feature_pack", {}) or {})
    raw_support_ledger = (
        feature_pack.get("state_support_ledger")
        if "state_support_ledger" in feature_pack
        else evidence_state.get("state_support_ledger")
    )
    state_support_ledger = (
        index_state_support_ledger(raw_support_ledger)
        if raw_support_ledger is not None
        else {}
    )
    source_asmae_grid_spec = feature_pack.get("grid_spec")
    target_grid_spec = getattr(l1_data, "grid_spec", None)
    if target_grid_spec is None and getattr(inp, "field_tensor", None) is not None:
        target_grid_spec = getattr(inp.field_tensor, "grid_spec", None)

    # Construct authoritative WGS84 geographic display grid from metric ASMAE grid spec
    # to avoid downsampling or clipping high-resolution (e.g. 2m) full-extent ASMAE surfaces.
    asmae_display_grid_spec = None
    if source_asmae_grid_spec and isinstance(source_asmae_grid_spec, dict):
        try:
            from rasterio.crs import CRS
            from rasterio.warp import transform_bounds
            s_crs_raw = source_asmae_grid_spec.get("crs")
            s_bounds = source_asmae_grid_spec.get("bounds")
            s_w = int(source_asmae_grid_spec.get("width", 0) or 0)
            s_h = int(source_asmae_grid_spec.get("height", 0) or 0)
            s_res = float(source_asmae_grid_spec.get("native_resolution_m", source_asmae_grid_spec.get("resolution_m", 2.0)) or 2.0)
            if s_crs_raw and s_bounds and s_w > 0 and s_h > 0:
                s_crs = CRS.from_user_input(s_crs_raw)
                if not s_crs.is_geographic:
                    dst_crs = CRS.from_user_input("EPSG:4326")
                    geo_bounds = list(transform_bounds(s_crs, dst_crs, *s_bounds))
                    dx = (geo_bounds[2] - geo_bounds[0]) / float(s_w)
                    dy = (geo_bounds[3] - geo_bounds[1]) / float(s_h)
                    asmae_display_grid_spec = {
                        "crs": "EPSG:4326",
                        "bounds": geo_bounds,
                        "transform": [geo_bounds[0], dx, 0.0, geo_bounds[3], 0.0, -dy],
                        "width": s_w,
                        "height": s_h,
                        "resolution_m": s_res,
                        "resolution": s_res,
                    }
                else:
                    asmae_display_grid_spec = dict(source_asmae_grid_spec)
        except Exception:
            asmae_display_grid_spec = None

    if target_grid_spec is None and asmae_display_grid_spec:
        target_grid_spec = asmae_display_grid_spec
        H = asmae_display_grid_spec["height"]
        W = asmae_display_grid_spec["width"]

    # Combine state and diagnostic surfaces to process
    all_asmae_types = list(ASMAE_STATE_SURFACES) + list(ASMAE_DIAGNOSTIC_SURFACES)

    # Palette mappings
    palettes = {
        SurfaceType.ASMAE_VIGOR: PaletteId.VIGOR_GREEN,
        getattr(SurfaceType, "CANOPY_ASMAE_VIGOR", SurfaceType.ASMAE_VIGOR): PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_LAI: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_CHLOROPHYLL: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_CANOPY_WATER: PaletteId.YIELD_BLUE,
        getattr(SurfaceType, "WATER_ASMAE_CANOPY_WATER", SurfaceType.ASMAE_CANOPY_WATER): PaletteId.YIELD_BLUE,
        SurfaceType.ASMAE_ROOT_ZONE_WATER: PaletteId.YIELD_BLUE,
        SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: PaletteId.YIELD_BLUE,
        SurfaceType.ASMAE_STRUCTURE: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_BARE_SOIL: PaletteId.CARBON_BROWN,
        SurfaceType.ASMAE_SALINITY_STRESS: PaletteId.SALINITY_TEAL,
        SurfaceType.ASMAE_THERMAL_STRESS: PaletteId.THERMAL_ORANGE,
        SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: PaletteId.STRESS_RED,
        SurfaceType.ASMAE_PHENOLOGY_PROGRESS: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_STRESS_MEMORY: PaletteId.STRESS_RED,
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_POSTERIOR_CONCENTRATION: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_UNCERTAINTY: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_RETROVALIDATION_SCORE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_BMA_DISAGREEMENT: PaletteId.RISK_HEAT,
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: PaletteId.RISK_HEAT,
        SurfaceType.ASMAE_EXPORT_ELIGIBILITY: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_1M_ADVISORY_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_UNCERTAINTY: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_RETROVALIDATION_SCORE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_BMA_DISAGREEMENT: PaletteId.RISK_HEAT,
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: PaletteId.RISK_HEAT,
        SurfaceType.ASMAE_EXPORT_ELIGIBILITY: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_1M_ADVISORY_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_5M_GENERALIZED_MASK: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: PaletteId.RAW_GRAYSCALE,
        SurfaceType.ASMAE_ML_AGREEMENT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_ARCHIVE_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_ENKF_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_BIOPHYSICAL_CLUSTERS: PaletteId.DECISION_CATEGORICAL,
        SurfaceType.ASMAE_WATER_RETENTION: PaletteId.YIELD_BLUE,
        SurfaceType.ASMAE_NUTRIENT_RESPONSE: PaletteId.VIGOR_GREEN,
        SurfaceType.ASMAE_SALINITY_PERSISTENCE: PaletteId.SALINITY_TEAL,
        SurfaceType.ASMAE_THERMAL_SENSITIVITY: PaletteId.THERMAL_ORANGE,
        SurfaceType.COMPOSITE_ADVISORY_CANOPY: PaletteId.VIGOR_GREEN,
        SurfaceType.COMPOSITE_VEG_ATTENTION: PaletteId.VIGOR_GREEN,
        SurfaceType.COMPOSITE_WATER_SUPPORT: PaletteId.YIELD_BLUE,
        SurfaceType.COMPOSITE_NUTRIENT_SUPPORT: PaletteId.VIGOR_GREEN,
        SurfaceType.COMPOSITE_SALINITY_STRESS: PaletteId.SALINITY_TEAL,
        SurfaceType.COMPOSITE_RISK_DIAGNOSTIC: PaletteId.RISK_HEAT,
        SurfaceType.COMPOSITE_CONFIDENCE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION: PaletteId.RAW_GRAYSCALE,
        SurfaceType.COMPOSITE_UNCERTAINTY: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_BMA_DISAGREEMENT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_ARCHIVE_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_RETRO_SCORE: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_ML_SUPPORT: PaletteId.UNCERTAINTY_GRAY,
        SurfaceType.COMPOSITE_TEXTURE_DETAIL: PaletteId.RAW_GRAYSCALE,
        SurfaceType.EXPERIMENTAL_TEXTURE_SUPPORT_MASK: PaletteId.RAW_GRAYSCALE,
    }

    # Unit mappings
    units = {
        SurfaceType.ASMAE_VIGOR: "fraction",
        getattr(SurfaceType, "CANOPY_ASMAE_VIGOR", SurfaceType.ASMAE_VIGOR): "fraction",
        SurfaceType.ASMAE_LAI: "index",
        SurfaceType.ASMAE_CHLOROPHYLL: "ug/cm2",
        SurfaceType.ASMAE_CANOPY_WATER: "fraction",
        getattr(SurfaceType, "WATER_ASMAE_CANOPY_WATER", SurfaceType.ASMAE_CANOPY_WATER): "fraction",
        SurfaceType.ASMAE_ROOT_ZONE_WATER: "fraction",
        SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: "fraction",
        SurfaceType.ASMAE_STRUCTURE: "fraction",
        SurfaceType.ASMAE_BARE_SOIL: "fraction",
        SurfaceType.ASMAE_SALINITY_STRESS: "fraction",
        SurfaceType.ASMAE_THERMAL_STRESS: "fraction",
        SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: "fraction",
        SurfaceType.ASMAE_PHENOLOGY_PROGRESS: "fraction",
        SurfaceType.ASMAE_STRESS_MEMORY: "fraction",
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: "meters",
        SurfaceType.ASMAE_POSTERIOR_CONCENTRATION: "fraction",
        SurfaceType.ASMAE_UNCERTAINTY: "fraction",
        SurfaceType.ASMAE_RETROVALIDATION_SCORE: "fraction",
        SurfaceType.ASMAE_BMA_DISAGREEMENT: "fraction",
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: "fraction",
        SurfaceType.ASMAE_EXPORT_ELIGIBILITY: "bool",
        SurfaceType.ASMAE_1M_ADVISORY_MASK: "fraction",
        SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: "fraction",
        SurfaceType.ASMAE_5M_GENERALIZED_MASK: "fraction",
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: "meters",
        SurfaceType.ASMAE_ML_AGREEMENT: "fraction",
        SurfaceType.ASMAE_ARCHIVE_SUPPORT: "fraction",
        SurfaceType.ASMAE_ENKF_SUPPORT: "fraction",
        SurfaceType.ASMAE_BIOPHYSICAL_CLUSTERS: "cluster_id",
        SurfaceType.ASMAE_WATER_RETENTION: "fraction",
        SurfaceType.ASMAE_NUTRIENT_RESPONSE: "fraction",
        SurfaceType.ASMAE_SALINITY_PERSISTENCE: "fraction",
        SurfaceType.ASMAE_THERMAL_SENSITIVITY: "fraction",
        SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: "fraction",
        SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: "fraction",
        SurfaceType.COMPOSITE_ADVISORY_CANOPY: "fraction",
        SurfaceType.COMPOSITE_VEG_ATTENTION: "fraction",
        SurfaceType.COMPOSITE_WATER_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_NUTRIENT_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_SALINITY_STRESS: "fraction",
        SurfaceType.COMPOSITE_RISK_DIAGNOSTIC: "fraction",
        SurfaceType.COMPOSITE_CONFIDENCE: "fraction",
        SurfaceType.COMPOSITE_EFFECTIVE_RESOLUTION: "meters",
        SurfaceType.COMPOSITE_UNCERTAINTY: "fraction",
        SurfaceType.COMPOSITE_BMA_DISAGREEMENT: "fraction",
        SurfaceType.COMPOSITE_ARCHIVE_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_RETRO_SCORE: "fraction",
        SurfaceType.COMPOSITE_ML_SUPPORT: "fraction",
        SurfaceType.COMPOSITE_TEXTURE_DETAIL: "fraction",
        SurfaceType.EXPERIMENTAL_TEXTURE_SUPPORT_MASK: "fraction",
    }

    render_ranges = {
        SurfaceType.ASMAE_LAI: (0.0, 8.0),
        SurfaceType.ASMAE_CHLOROPHYLL: (0.0, 80.0),
        SurfaceType.ASMAE_PHENOLOGY_PROGRESS: (0.0, 1.0),
        SurfaceType.ASMAE_STRESS_MEMORY: (0.0, 1.0),
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: (0.03, 10.0),
    }

    from services.agribrain.scientific_contracts.state_schema_ref import canonical_state_key

    for stype in all_asmae_types:
        var_name = stype.value.lower()
        canon_state = canonical_state_key(stype.value)
        meta_candidates = [var_name, var_name.upper(), var_name.lower(), stype.value]
        if canon_state and canon_state != "unmapped":
            meta_candidates.extend([
                canon_state, canon_state.upper(), canon_state.lower(),
                f"asmae_{canon_state}", f"asmae_{canon_state}".upper(), f"asmae_{canon_state}".lower(),
            ])
        if stype == SurfaceType.ASMAE_BARE_SOIL:
            meta_candidates.extend(["asmae_bare_soil_fraction", "bare_soil_fraction", "ASMAE_BARE_SOIL_FRACTION"])

        # Look up metadata case-insensitively
        meta = {}
        for key in meta_candidates:
            if key in l1_data.raster_metadata:
                meta = l1_data.raster_metadata[key]
                break

        # Check for grid in raster_maps
        grid = None
        has_real_grid = False
        
        # Map variables to their actual raster keys in L1 raster_maps
        l1_grid_keys = list(dict.fromkeys([*meta_candidates, var_name, var_name.upper(), var_name.lower(), stype.value]))
        if stype in (SurfaceType.ASMAE_VIGOR, getattr(SurfaceType, "CANOPY_ASMAE_VIGOR", None)):
            l1_grid_keys.extend(["asmae_vigor", "canopy_asmae_vigor", "vigor"])
        if stype in (SurfaceType.ASMAE_CANOPY_WATER, getattr(SurfaceType, "WATER_ASMAE_CANOPY_WATER", None)):
            l1_grid_keys.extend(["asmae_canopy_water", "water_asmae_canopy_water", "canopy_water"])
        # Standardize state aliases
        if stype == SurfaceType.ASMAE_BARE_SOIL:
            l1_grid_keys.extend(["asmae_bare_soil_fraction", "asmae_bare_soil", "bare_soil_fraction"])
        if stype == SurfaceType.ASMAE_PHENOLOGY_PROGRESS:
            l1_grid_keys.extend(["asmae_phenology_progress", "phenology_progress", "phenology"])
        if stype == SurfaceType.ASMAE_STRESS_MEMORY:
            l1_grid_keys.extend(["asmae_stress_memory", "stress_memory", "memory"])

        for key in l1_grid_keys:
            if key in l1_data.raster_maps:
                grid = l1_data.raster_maps[key]
                has_real_grid = True
                break

        # Fallback to metadata / scalar last_values
        scalar_val = None
        for key in meta_candidates:
            if key in l1_data.last_values:
                scalar_val = l1_data.last_values[key]
                break

        # P0-2 Presence Gating: Only generate if has_real_grid, has_scalar, or has_metadata
        has_grid_presence = has_real_grid
        has_scalar_presence = scalar_val is not None
        has_metadata_presence = bool(meta)

        if not (has_grid_presence or has_scalar_presence or has_metadata_presence):
            continue

        is_state_surface = stype in ASMAE_STATE_SURFACES

        if is_state_surface and not has_real_grid:
            # Rule: do not broadcast scalar fallback for state surfaces
            grid = [[None] * W for _ in range(H)]
            has_spatial_grid_flag = False
            generated_from = "metadata_fallback"
            diagnostic_only = True
            state_update_allowed = False
            presc_driver_allowed = False
            visual_only = True
        else:
            has_spatial_grid_flag = True
            generated_from = "raster_maps" if has_real_grid else "metadata_fallback"
            
            if not has_real_grid:
                # Allowed to broadcast diagnostic/metadata surfaces
                val = scalar_val if scalar_val is not None else (10.0 if stype == SurfaceType.ASMAE_EFFECTIVE_RESOLUTION else 0.0)
                grid = [[val] * W for _ in range(H)]
            
            # Multi-carrier inspection for meta permissions
            meta_su = []
            for k in ("state_update_allowed", "stateUpdateAllowed"):
                if k in meta:
                    meta_su.append(_parse_strict_bool(meta[k]))
            if False in meta_su:
                state_update_allowed = False
            elif True in meta_su:
                state_update_allowed = True
            else:
                state_update_allowed = False

            meta_presc = []
            for k in ("prescription_driver_allowed", "prescriptionDriverAllowed"):
                if k in meta:
                    meta_presc.append(_parse_strict_bool(meta[k]))
            if False in meta_presc:
                presc_driver_allowed = False
            elif True in meta_presc:
                presc_driver_allowed = True
            else:
                presc_driver_allowed = False

            meta_diag = []
            for k in ("diagnostic_only", "diagnosticOnly"):
                if k in meta:
                    meta_diag.append(_parse_strict_bool(meta[k]))
            if True in meta_diag:
                diagnostic_only = True
            elif False in meta_diag:
                diagnostic_only = False
            else:
                diagnostic_only = True
            visual_only = False

        # Extract parameters None-safely
        confidence_available = bool(meta.get("calibrated_confidence_available", meta.get("posterior_confidence_available", False)))
        uncertainty_available = bool(meta.get("posterior_uncertainty_available", meta.get("uncertainty") is not None))

        # E-D01: State-specific uncertainty grid & confidence binding
        state_key = var_name[len("asmae_"):] if var_name.startswith("asmae_") else var_name
        search_state_keys = [state_key]
        if canon_state and canon_state != "unmapped" and canon_state not in search_state_keys:
            search_state_keys.append(canon_state)
        if state_key == "bare_soil" and "bare_soil_fraction" not in search_state_keys:
            search_state_keys.append("bare_soil_fraction")
        elif state_key == "bare_soil_fraction" and "bare_soil" not in search_state_keys:
            search_state_keys.append("bare_soil")

        own_unc_grid = None
        own_conf_grid = None
        if l1_data and hasattr(l1_data, "raster_maps"):
            for sk in search_state_keys:
                if own_unc_grid is None:
                    own_unc_grid = (
                        l1_data.raster_maps.get(f"asmae_{sk}_uncertainty")
                        or l1_data.raster_maps.get(f"{sk}_uncertainty")
                    )
                if own_conf_grid is None:
                    own_conf_grid = (
                        l1_data.raster_maps.get(f"asmae_{sk}_confidence")
                        or l1_data.raster_maps.get(f"{sk}_confidence")
                    )
                if own_unc_grid is not None and own_conf_grid is not None:
                    break

        if own_unc_grid is not None:
            unc_finite = [
                float(v) for row in own_unc_grid for v in row
                if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            ]
            if unc_finite:
                uncertainty = sum(unc_finite) / len(unc_finite)
            else:
                raw_unc = meta.get("uncertainty")
                uncertainty = float(raw_unc) if raw_unc is not None else 1.0
        else:
            raw_unc = meta.get("uncertainty")
            uncertainty = float(raw_unc) if raw_unc is not None else 1.0

        if own_conf_grid is not None:
            conf_finite = [
                float(v) for row in own_conf_grid for v in row
                if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            ]
            if conf_finite:
                confidence = sum(conf_finite) / len(conf_finite)
            else:
                raw_conf = meta.get("posterior_concentration", meta.get("confidence"))
                confidence = float(raw_conf) if raw_conf is not None else 0.0
        else:
            raw_conf = meta.get("posterior_concentration", meta.get("confidence"))
            confidence = float(raw_conf) if raw_conf is not None else 0.0

        resolution_m = float(meta.get("resolution_m", 10.0))
        asmae_channel = meta.get("asmae_channel", "diagnostic")
        source_basis = meta.get("source_basis", "asmae")
        c_hash = meta.get("content_hash")
        a_hash = meta.get("artifact_instance_hash")
        retro_status = meta.get("retro_status")
        retro_score = float(meta.get("retro_mean_score", meta.get("retrovalidation_score", 0.0)))
        bma_status = meta.get("bma_status")
        bma_disagreement = float(meta.get("bma_disagreement", 0.0))
        cross_layer_conflict = float(meta.get("cross_layer_conflict", 0.0))

        # Scene stack and validation parameters
        # V92.4-BC: No safe defaults. Missing proof must propagate as None
        # so asmae_surface_spatially_eligible() rejects correctly.
        scene_stack_mode = meta.get("scene_stack_mode") or meta.get("scene_stack_status_mode")
        degraded_mean_only = meta.get("degraded_mean_only", scene_stack_mode == "degraded_mean_only") if scene_stack_mode else False
        no_scenes = meta.get("no_scenes", scene_stack_mode == "no_scenes") if scene_stack_mode else False
        mean_only = meta.get("mean_only", False)
        operator_locked = meta.get("operator_locked")
        graph_locked = meta.get("graph_locked")
        radiometric_mode = meta.get("radiometric_mode")
        enkf_mode = meta.get("enkf_mode")

        # Enforce visual-only limits for 1m overlays, checking resolver for V90
        is_certified_v90 = False
        resolved_result = None
        if resolution_m <= 1.0:
            cert_id = meta.get("certification_id")
            cert_src = meta.get("certification_source")
            cert_status = meta.get("certification_status")
            
            # Map variable
            v90_var = get_standard_variable_name(stype, meta.get("variable"))
            
            # Get geometry hash and crop season
            geom_hash = ""
            if hasattr(inp, "field_tensor"):
                geom_hash = getattr(inp.field_tensor, "geometry_hash", "")
                if not geom_hash and hasattr(inp.field_tensor, "_context_package"):
                    geom_hash = getattr(inp.field_tensor._context_package, "geometry_hash", "")
            if not geom_hash:
                geom_hash = getattr(inp, "geometry_hash", "")
                
            crop_season_id = getattr(inp, "crop_season_id", "")
            if not crop_season_id and hasattr(inp, "field_tensor"):
                crop_season_id = getattr(inp.field_tensor, "crop_season_id", "")
                if not crop_season_id and hasattr(inp.field_tensor, "_context_package"):
                    crop_season_id = getattr(inp.field_tensor._context_package, "crop_season_id", "")
            if not crop_season_id:
                crop_season_id = meta.get("crop_season_id", "")

            source_hashes = {
                "layer0_output_hash": meta.get("layer0_output_hash", ""),
                "asmae_content_hash": meta.get("asmae_content_hash", ""),
                "asmae_artifact_instance_hash": meta.get("asmae_artifact_instance_hash", ""),
                "memory_content_hash": meta.get("memory_content_hash", ""),
                "report_verified_evidence_hash": meta.get("report_verified_evidence_hash", ""),
            }

            # Call V90 resolver
            from certification.v90_resolver import verify_v90_certification_record
            resolved_result = verify_v90_certification_record(
                certification_id=cert_id,
                plot_id=inp.plot_id,
                variable=v90_var,
                time_window=(meta.get("time_window_start"), meta.get("time_window_end")),
                geometry_hash=geom_hash,
                crop_season_id=crop_season_id,
                source_hashes=source_hashes
            )
            
            if cert_src == "v90" and cert_status == "certified" and cert_id and resolved_result.approved:
                is_certified_v90 = True
                
            if is_certified_v90:
                visual_only = False
                diagnostic_only = True
                state_update_allowed = False  # force-blocked!
                asmae_channel = "certified_inferred_detail"
                certification_status = "certified_inferred_detail"
            else:
                visual_only = True
                diagnostic_only = True
                state_update_allowed = False
                asmae_channel = "visual"
                certification_status = "uncertified_1m"

        # Apply display trust policy
        policy = get_surface_display_policy(
            confidence=confidence,
            uncertainty=uncertainty,
            resolution_m=resolution_m,
            bma_status=bma_status,
            cross_layer_conflict=cross_layer_conflict,
            is_certified_v90=is_certified_v90
        )

        # P0-4 Certified observation basis calculation
        native_basis = meta.get("native_observation_resolution_m", 10.0)
        certified_basis_m = meta.get("certified_basis_m", native_basis)

        # P1-1 Non-empty warning wording logic
        warning_wording = ""
        if policy["requires_user_warning"] or resolution_m <= 1.0:
            wordings = []
            if "resolution_1m_blocked" in policy["warning_codes"]:
                wordings.append("Experimental visual detail — not a direct 1m satellite observation.")
            if "cross_layer_conflict" in policy["warning_codes"]:
                wordings.append("ASMAE conflicts with other evidence sources.")
            if "low_confidence" in policy["warning_codes"]:
                wordings.append("Low-confidence ASMAE surface. Use as diagnostic context.")
            if "high_uncertainty" in policy["warning_codes"]:
                wordings.append("High uncertainty. Interpret boundaries cautiously.")
            if "bma_not_success" in policy["warning_codes"]:
                wordings.append("Model agreement was insufficient; this layer is diagnostic.")
            if "mild_warning" in policy["warning_codes"]:
                wordings.append("Provisional ASMAE evidence with mild warnings.")
            
            if wordings:
                warning_wording = " ".join(wordings)
            else:
                warning_wording = "ASMAE quality warning."

        # In both cases, append the warning: "Certified inferred high-resolution detail; not a direct 1m satellite observation."
        if resolution_m <= 1.0:
            msg = "Certified inferred high-resolution detail; not a direct 1m satellite observation."
            if warning_wording:
                warning_wording += " " + msg
            else:
                warning_wording = msg

        # Determine real_asmae_evidence and source_reality
        real_ev = getattr(l1_data, "real_asmae_evidence", False)
        src_real = "raster_composite_proxy"
        if real_ev:
            src_real = "real_raster"
            if l1_data.asmae_evidence_state:
                src_real = l1_data.asmae_evidence_state.get("source_reality", "real_raster")
        elif l1_data.asmae_evidence_state:
            src_real = l1_data.asmae_evidence_state.get("source_reality", "raster_composite_proxy")

        creator_mapping = {
            SurfaceType.ASMAE_VIGOR: "ASMAE_ENKF",
            SurfaceType.ASMAE_LAI: "ASMAE_ENKF",
            SurfaceType.ASMAE_CHLOROPHYLL: "ASMAE_ENKF",
            SurfaceType.ASMAE_CANOPY_WATER: "ASMAE_ENKF",
            SurfaceType.ASMAE_ROOT_ZONE_WATER: "ASMAE_ENKF",
            SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: "ASMAE_ENKF",
            SurfaceType.ASMAE_STRUCTURE: "ASMAE_ENKF",
            SurfaceType.ASMAE_BARE_SOIL: "ASMAE_ENKF",
            SurfaceType.ASMAE_SALINITY_STRESS: "ASMAE_ENKF",
            SurfaceType.ASMAE_THERMAL_STRESS: "ASMAE_ENKF",
            SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: "ASMAE_ENKF",
            SurfaceType.ASMAE_PHENOLOGY_PROGRESS: "ASMAE_ENKF",
            SurfaceType.ASMAE_STRESS_MEMORY: "ASMAE_ENKF",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: "ASMAE_ENKF",
            SurfaceType.ASMAE_POSTERIOR_CONCENTRATION: "ASMAE_BMA",
            SurfaceType.ASMAE_UNCERTAINTY: "ASMAE_BMA",
            SurfaceType.ASMAE_RETROVALIDATION_SCORE: "ASMAE_RETROVALIDATION",
            SurfaceType.ASMAE_BMA_DISAGREEMENT: "ASMAE_BMA",
            SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: "ASMAE_ML",
            SurfaceType.ASMAE_EXPORT_ELIGIBILITY: "ASMAE_ENKF",
            SurfaceType.ASMAE_1M_ADVISORY_MASK: "ASMAE_ENKF",
            SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: "ASMAE_ENKF",
            SurfaceType.ASMAE_5M_GENERALIZED_MASK: "ASMAE_ENKF",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: "ASMAE_ENKF",
            SurfaceType.ASMAE_ML_AGREEMENT: "ASMAE_ML",
            SurfaceType.ASMAE_ARCHIVE_SUPPORT: "ASMAE_ARCHIVE",
            SurfaceType.ASMAE_ENKF_SUPPORT: "ASMAE_ENKF",
            SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: "ASMAE_RADIOMETRIC",
            SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: "ASMAE_VISUAL_FUSION",
            SurfaceType.ASMAE_BIOPHYSICAL_CLUSTERS: "ASMAE_MICROZONE",
            SurfaceType.ASMAE_WATER_RETENTION: "ASMAE_MICROZONE",
            SurfaceType.ASMAE_NUTRIENT_RESPONSE: "ASMAE_MICROZONE",
            SurfaceType.ASMAE_SALINITY_PERSISTENCE: "ASMAE_MICROZONE",
            SurfaceType.ASMAE_THERMAL_SENSITIVITY: "ASMAE_MICROZONE",
        }

        feature_mapping = {
            SurfaceType.ASMAE_VIGOR: "asmae_vigor",
            SurfaceType.ASMAE_LAI: "asmae_lai",
            SurfaceType.ASMAE_CHLOROPHYLL: "asmae_chlorophyll",
            SurfaceType.ASMAE_CANOPY_WATER: "asmae_canopy_water",
            SurfaceType.ASMAE_ROOT_ZONE_WATER: "asmae_root_zone_water",
            SurfaceType.ASMAE_SURFACE_WETNESS_EVENT: "asmae_surface_wetness_event",
            SurfaceType.ASMAE_STRUCTURE: "asmae_structure",
            SurfaceType.ASMAE_BARE_SOIL: "asmae_bare_soil",
            SurfaceType.ASMAE_SALINITY_STRESS: "asmae_salinity_stress",
            SurfaceType.ASMAE_THERMAL_STRESS: "asmae_thermal_stress",
            SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: "asmae_biotic_confounder_risk",
            SurfaceType.ASMAE_PHENOLOGY_PROGRESS: "asmae_phenology_progress",
            SurfaceType.ASMAE_STRESS_MEMORY: "asmae_stress_memory",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: "asmae_effective_resolution",
            SurfaceType.ASMAE_POSTERIOR_CONCENTRATION: "asmae_posterior_concentration",
            SurfaceType.ASMAE_UNCERTAINTY: "asmae_uncertainty",
            SurfaceType.ASMAE_RETROVALIDATION_SCORE: "retrovalidation_score",
            SurfaceType.ASMAE_BMA_DISAGREEMENT: "bma_disagreement",
            SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: "cross_layer_conflict",
            SurfaceType.ASMAE_EXPORT_ELIGIBILITY: "asmae_export_eligibility",
            SurfaceType.ASMAE_1M_ADVISORY_MASK: "asmae_1m_advisory_mask",
            SurfaceType.ASMAE_2_5M_MODEL_ASSISTED_MASK: "asmae_2_5m_model_assisted_mask",
            SurfaceType.ASMAE_5M_GENERALIZED_MASK: "asmae_5m_generalized_mask",
            SurfaceType.ASMAE_EFFECTIVE_RESOLUTION_MAP: "asmae_effective_resolution_map",
            SurfaceType.ASMAE_ML_AGREEMENT: "ml_agreement",
            SurfaceType.ASMAE_ARCHIVE_SUPPORT: "archive_support",
            SurfaceType.ASMAE_ENKF_SUPPORT: "enkf_support",
            SurfaceType.ASMAE_RADIOMETRIC_SUPPORT: "radiometric_support",
            SurfaceType.ASMAE_VISUAL_FUSION_CANOPY: "visual_fusion_canopy",
            SurfaceType.ASMAE_BIOPHYSICAL_CLUSTERS: "biophysical_clusters",
            SurfaceType.ASMAE_WATER_RETENTION: "water_retention",
            SurfaceType.ASMAE_NUTRIENT_RESPONSE: "nutrient_response",
            SurfaceType.ASMAE_SALINITY_PERSISTENCE: "salinity_persistence",
            SurfaceType.ASMAE_THERMAL_SENSITIVITY: "thermal_sensitivity",
        }

        support_meta = compute_asmae_support_classification(
            real_ev=real_ev,
            source_reality=src_real,
            meta=meta,
            stype=stype,
            state_support_ledger=state_support_ledger,
            feature_name=feature_mapping.get(stype, var_name),
        )

        surf_blocks = []
        for b_source in (
            meta.get("block_reasons"),
            meta.get("blockReasons"),
            meta.get("restriction_reasons"),
            meta.get("restrictionReasons"),
            meta.get("exclusion_reason"),
            meta.get("exclusionReason"),
            meta.get("authority_block_reason"),
            meta.get("authorityBlockReason"),
            support_meta.get("block_reasons") if isinstance(support_meta, dict) else None,
        ):
            if b_source:
                if isinstance(b_source, (list, tuple, set)):
                    for b in b_source:
                        if b and str(b) not in surf_blocks:
                            surf_blocks.append(str(b))
                elif isinstance(b_source, str) and b_source:
                    if b_source not in surf_blocks:
                        surf_blocks.append(b_source)

        provenance = {
            "real_asmae_evidence": real_ev,
            "source_reality": src_real,
            "support_class": support_meta["support_class"],
            "evidence_class": support_meta["evidence_class"],
            "authority_ceiling": support_meta.get("authority_ceiling"),
            "direct_observation": support_meta["direct_observation"],
            "scouting_zone_eligible": support_meta["scouting_zone_eligible"],
            "management_zone_eligible": support_meta["management_zone_eligible"],
            "zone_statistics_eligible": support_meta["zone_statistics_eligible"],
            "creator": creator_mapping.get(stype, "ASMAE_ENKF"),
            "asmae_feature": feature_mapping.get(stype, stype.value.lower()),
            "used_bma": bool(meta.get("used_bma", evidence_state.get("used_bma", False))),
            "used_archive": bool(meta.get("used_archive", evidence_state.get("used_archive", False))),
            "used_retrovalidation": bool(meta.get("used_retrovalidation", evidence_state.get("used_retrovalidation", False))),
            "used_ml": bool(meta.get("used_ml", evidence_state.get("used_ml", False))),
            "has_spatial_grid": has_spatial_grid_flag,
            # The surface receives an explicit, validated display grid below.
            # Inheriting a later output grid would sever that proof.
            "grid_inheritance_allowed": False,
            "surface_generated_from": generated_from,
            "surface_type": stype.value,
            "render_mode": f"RenderMode.{stype.value}",
            "asmae_channel": asmae_channel,
            "resolution_m": resolution_m,
            "effective_resolution_m": meta.get("effective_resolution_m", resolution_m),
            "native_observation_resolution_m": native_basis,
            "certified_basis_m": certified_basis_m,
            "source_basis": source_basis,
            "confidence": confidence,
            "uncertainty": own_unc_grid if own_unc_grid is not None else uncertainty,
            "uncertainty_grid": own_unc_grid,
            "confidence_grid": own_conf_grid,
            "diagnostic_uncertainty": meta.get("diagnostic_uncertainty", meta.get("posterior_uncertainty")),
            "normalized_uncertainty": meta.get("normalized_uncertainty", meta.get("posterior_uncertainty")),
            "state_uncertainty_scalar": uncertainty,
            "posterior_confidence_available": confidence_available,
            "posterior_uncertainty_available": uncertainty_available,
            "retro_status": retro_status,
            "retrovalidation_score": retro_score,
            "bma_status": bma_status,
            "bma_disagreement": bma_disagreement,
            "cross_layer_conflict": cross_layer_conflict,
            "state_update_allowed": state_update_allowed,
            "prescription_driver_allowed": presc_driver_allowed,
            "enkf_mode": enkf_mode,
            "radiometric_mode": radiometric_mode,
            "operator_locked": operator_locked,
            "graph_locked": graph_locked,
            "scene_stack_mode": scene_stack_mode,
            "degraded_mean_only": degraded_mean_only,
            "no_scenes": no_scenes,
            "mean_only": mean_only,
            "operator_bundle_hash": meta.get("operator_bundle_hash"),
            "has_enkf_proxy_fallback": meta.get("has_enkf_proxy_fallback", False),
            "full_enkf_credit_allowed": meta.get("full_enkf_credit_allowed", False),
            "full_radiometric_credit_allowed": meta.get("full_radiometric_credit_allowed", False),
            "diagnostic_only": diagnostic_only,
            "visual_only": visual_only,
            "content_hash": c_hash,
            "artifact_instance_hash": a_hash,
            "warning_codes": policy["warning_codes"],
            "display_trust_tier": policy["display_trust_tier"],
            "desaturation_level": policy["desaturation_level"],
            "alpha_multiplier": policy["alpha_multiplier"],
            "requires_user_warning": policy["requires_user_warning"],
            "warning_wording": warning_wording,
        }
        if surf_blocks:
            provenance["block_reasons"] = list(surf_blocks)

        surface_source_grid_spec = None
        surface_display_grid_spec = None
        if has_real_grid:
            resampling_method = (
                "nearest" if stype in _ASMAE_NEAREST_RESAMPLE_TYPES else "bilinear"
            )
            try:
                (
                    grid,
                    surface_source_grid_spec,
                    surface_display_grid_spec,
                    alignment_proof,
                ) = _align_asmae_grid_to_target(
                    grid,
                    source_grid_spec=_source_grid_spec_for_surface(
                        meta, source_asmae_grid_spec
                    ),
                    target_grid_spec=target_grid_spec,
                    target_height=H,
                    target_width=W,
                    method=resampling_method,
                )
            except ValueError as exc:
                # Omit only this unproven surface. Never transpose/reshape it,
                # and do not erase independently valid ASMAE candidates.
                _record_alignment_failure(
                    l1_data,
                    surface_type=stype,
                    variable=var_name,
                    reason=str(exc),
                )
                continue
            provenance.update(alignment_proof)

        # The advisory mask is an inter-stage control artifact, not just a
        # renderable raster.  Bind it to the exact ASMAE snapshot, authority
        # decision and grid that produced it so a later stage can fail closed
        # instead of consuming a stale, proxy-derived or resampled mask.
        if stype == SurfaceType.ASMAE_1M_ADVISORY_MASK:
            evidence_state = dict(getattr(l1_data, "asmae_evidence_state", {}) or {})
            allowed_outputs = evidence_state.get("allowed_outputs") or []
            source_plot_id = meta.get("source_plot_id") or inp.plot_id
            source_schema_version = meta.get("source_schema_version")
            authority = evidence_state.get("authority")
            current_1m_allowed = bool(evidence_state.get("current_1m_approval_allowed", False))
            output_allowed = (
                "ASMAE_1M_ADVISORY_MASK" in allowed_outputs
                if allowed_outputs
                else current_1m_allowed
            )
            non_proxy = bool(
                real_ev
                and evidence_state.get("real_asmae_evidence", False)
                and src_real not in ("raster_composite_proxy", "proxy", "synthetic", "unknown", "missing")
                and "proxy" not in str(src_real).lower()
            )
            provenance["candidate_mask_proof"] = {
                "contract_version": "asmae_candidate_mask_v1",
                "source_schema_version": source_schema_version,
                "plot_id": str(source_plot_id or ""),
                "source_output_content_hash": c_hash,
                "source_artifact_instance_hash": a_hash,
                "source_generated_at": meta.get("source_generated_at"),
                "grid_shape": [H, W],
                "surface_grid_ref": f"{H}x{W}",
                "generated_from_current_raster": bool(has_real_grid and generated_from == "raster_maps"),
                "source_reality": src_real,
                "real_asmae_evidence": bool(real_ev and evidence_state.get("real_asmae_evidence", False)),
                "non_proxy": non_proxy,
                "authority": authority,
                "current_1m_authority_allowed": current_1m_allowed,
                "output_allowed": bool(output_allowed),
                "diagnostic_only": bool(diagnostic_only),
                "state_update_allowed": False,
            }

        # Inject explicit display-only and certification metadata
        if resolution_m <= 1.0:
            if resolved_result:
                provenance["certification_reason_codes"] = resolved_result.reason_codes
            if is_certified_v90:
                provenance["certification_status"] = "certified_inferred_detail"
                provenance["certification_source"] = "v90"
                provenance["certification_id"] = meta.get("certification_id")
                provenance["display_certified"] = True
                provenance["reporting_certified"] = True
                provenance["state_update_allowed"] = False
                provenance["layer1_state_evidence_allowed"] = False
                provenance["training_label_allowed"] = False
                provenance["prescription_driver_allowed"] = False
                provenance["not_direct_observation"] = True
            else:
                provenance["certification_status"] = "uncertified_1m"
                provenance["display_certified"] = False
                provenance["reporting_certified"] = False
                provenance["state_update_allowed"] = False
                provenance["layer1_state_evidence_allowed"] = False
                provenance["training_label_allowed"] = False
                provenance["prescription_driver_allowed"] = False
                provenance["not_direct_observation"] = True

        # Styling/wording overrides for visual_only 1m resolution or certified
        if resolution_m <= 1.0:
            if is_certified_v90:
                provenance["user_facing_badge"] = "Certified Inferred Detail"
                provenance["user_facing_warning"] = "Certified inferred detail; not a direct 1m observation"
                provenance["expert_tooltip"] = "Certified inferred detail from ASMAE deconvolution; display only"
                provenance["pixel_inspector_label"] = "Certified inferred detail; state update blocked"
                provenance["warning_wording"] = "Certified inferred high-resolution detail; not a direct 1m satellite observation."
            else:
                provenance["user_facing_badge"] = "Experimental visual detail"
                provenance["user_facing_warning"] = "Not a direct 1m satellite observation"
                provenance["expert_tooltip"] = "Inferred visual detail from ASMAE deconvolution / assimilation"
                provenance["pixel_inspector_label"] = "Visual-only; state update blocked"
                provenance["warning_wording"] = "Experimental visual detail — not a direct 1m satellite observation."

        # Grounding class
        flat_vals = [v for row in grid for v in row if v is not None]
        if not has_spatial_grid_flag:
            grounding = GroundingClass.UNIFORM.value
        elif len(set(flat_vals)) > 1:
            grounding = GroundingClass.RASTER_GROUNDED.value
        else:
            grounding = GroundingClass.UNIFORM.value

        if grounding == GroundingClass.UNIFORM.value:
            provenance["scope"] = "plot_level"
            provenance["constant_allowed"] = True

        has_blocks = len(surf_blocks) > 0
        state_update_req = _parse_strict_bool(provenance.get("state_update_allowed"))
        presc_req = _parse_strict_bool(provenance.get("prescription_driver_allowed"))

        # Bind support class: unsupported or derived diagnostic cannot have active permissions
        if support_meta.get("support_class") in ("unsupported", "derived_diagnostic"):
            state_update_req = False
            presc_req = False

        from services.agribrain.layer10_sire.surface_contract import _normalize_ceiling_token
        auth_ceil = _normalize_ceiling_token(provenance.get("authority_ceiling") or support_meta.get("authority_ceiling"))
        if auth_ceil in ("VISUALIZATION", "MONITORING_ONLY", "DIAGNOSTIC", "TRAINING_EXPORT"):
            state_update_req = False
            presc_req = False
        elif auth_ceil == "STATE_UPDATE":
            presc_req = False
        elif auth_ceil and auth_ceil not in ("PRESCRIPTION_DRIVER", "PRESCRIPTION_ELIGIBLE", "MANAGED_PRESCRIPTION", "FIELD_PRESCRIPTION", "FULL_SYSTEM_AUTONOMOUS"):
            # Unknown ceiling -> fail-closed
            state_update_req = False
            presc_req = False

        # Static descriptor ceiling intersection
        from services.agribrain.layer05_asmae.state.descriptors import STATE_DESCRIPTOR_BY_NAME
        from services.agribrain.scientific_contracts.state_schema_ref import canonical_state_key
        canon_name = canonical_state_key(feature_mapping.get(stype, var_name) or stype.value)
        desc = STATE_DESCRIPTOR_BY_NAME.get(canon_name)
        if desc and desc.authority_ceiling:
            desc_ceil_tok = _normalize_ceiling_token(desc.authority_ceiling)
            if desc_ceil_tok in ("VISUALIZATION", "MONITORING_ONLY", "DIAGNOSTIC", "TRAINING_EXPORT"):
                state_update_req = False
                presc_req = False
            elif desc_ceil_tok == "STATE_UPDATE":
                presc_req = False

        if provenance.get("diagnostic_only") is True:
            state_update_req = False
            presc_req = False

        surf_state_update = state_update_req and not has_blocks
        surf_prescription = presc_req and not has_blocks
        provenance["state_update_allowed"] = surf_state_update
        provenance["prescription_driver_allowed"] = surf_prescription
        surfaces.append(SurfaceArtifact(
            surface_id=f"{stype.value}_{inp.plot_id}",
            semantic_type=stype,
            grid_ref=f"{H}x{W}",
            values=grid,
            units=units[stype],
            native_resolution_m=resolution_m,
            render_range=render_ranges.get(stype, (0.0, 1.0)),
            palette_id=palettes[stype],
            source_layers=["L1"],
            provenance=provenance,
            state_update_allowed=surf_state_update,
            prescription_driver_allowed=surf_prescription,
            grounding_class=grounding,
            grid_spec=surface_display_grid_spec,
            source_grid_spec=surface_source_grid_spec,
            display_grid_spec=surface_display_grid_spec,
            block_reasons=list(surf_blocks) if surf_blocks else None,
        ))

    return surfaces


def asmae_surface_visual_eligible(surface: SurfaceArtifact) -> tuple[bool, str]:
    """Check if ASMAE surface is eligible for any visual display (card, badge, tint, or overlay).
    
    V92.4-BC.2: Soft visual gate. Only blocks when the surface genuinely has no
    renderable information at all. Passed surfaces may still be plot-level cards,
    metadata badges, or uniform tints — they are not necessarily pixel overlays.
    """
    if surface is None:
        return False, "surface_is_none"
    
    prov = surface.provenance or {}
    
    # No values at all — nothing to show
    vals = surface.values
    if not vals:
        return False, "no_values"
    
    # Check for at least one 2D array with finite values
    is_2d = isinstance(vals, list) and len(vals) > 0 and isinstance(vals[0], list)
    if not is_2d:
        return False, "no_2d_values"
    
    finite_count = sum(
        1 for row in vals for v in row
        if v is not None and isinstance(v, (int, float)) and not (isinstance(v, float) and (v != v))  # NaN check
    )
    if finite_count == 0:
        return False, "no_finite_values"
    
    return True, "visual_eligible"


def asmae_surface_pixel_visual_eligible(surface: SurfaceArtifact, output_grid_spec: Optional[dict] = None) -> tuple[bool, str]:
    """Check if ASMAE surface can render as a spatial pixel overlay (not just card/badge).
    
    V92.4-BC.2: Requires spatial grid and non-uniform grounding. Does NOT check
    authority gates (operator lock, radiometric mode, EnKF credit). Those are for
    state updates, prescriptions, and certification only.
    
    Surfaces that fail this check but pass visual_eligible can still appear as
    plot-level uniform tints or metadata cards.
    """
    # Must first pass basic visual eligibility
    visual_ok, visual_reason = asmae_surface_visual_eligible(surface)
    if not visual_ok:
        return False, visual_reason
    
    prov = surface.provenance or {}
    
    # Grounding class check — UNIFORM/BROADCAST cannot be pixel overlays
    gc = getattr(surface, "grounding_class", "UNIFORM") or "UNIFORM"
    if gc in ["UNIFORM", "BROADCAST"]:
        return False, "grounding_class_non_spatial"
    
    # Hard rejections for degraded states — no real spatial variation
    if prov.get("degraded_mean_only") is True:
        return False, "degraded_mean_only"
    if prov.get("no_scenes") is True:
        return False, "no_scenes"
    if prov.get("mean_only") is True:
        return False, "mean_only"
    
    # Require explicit spatial grid proof
    if prov.get("has_spatial_grid") is not True:
        return False, "no_spatial_grid"
    
    # Check grid_spec/bounds exist if surface has grid_spec attribute
    grid_spec = getattr(surface, "grid_spec", None)
    if not grid_spec:
        if not output_grid_spec:
            return False, "missing_grid_spec"
        # Check values shape matches output_grid_spec height and width
        vals = surface.values
        vals_h = len(vals) if vals else 0
        vals_w = len(vals[0]) if vals_h > 0 and isinstance(vals[0], list) else 0
        tgt_h = output_grid_spec.get("height", 0)
        tgt_w = output_grid_spec.get("width", 0)
        if vals_h != tgt_h or vals_w != tgt_w:
            if prov.get("grid_inheritance_allowed") is not True:
                return False, "grid_spec_shape_mismatch"
        if prov.get("grid_inheritance_allowed") is not True:
            return False, "grid_spec_not_provenanced"
        grid_spec = output_grid_spec
        
    if not grid_spec or not isinstance(grid_spec, dict):
        return False, "invalid_grid_spec"
        
    bounds = grid_spec.get("bounds")
    width = grid_spec.get("width")
    height = grid_spec.get("height")
    
    if not bounds or not isinstance(bounds, (list, tuple)) or len(bounds) < 4:
        return False, "missing_grid_spec_bounds"
    if not width or not isinstance(width, int) or width <= 0:
        return False, "missing_grid_spec_width"
    if not height or not isinstance(height, int) or height <= 0:
        return False, "missing_grid_spec_height"
    
    return True, "overlay_eligible"


def asmae_surface_spatially_eligible(surface: SurfaceArtifact) -> tuple[bool, str]:
    """Check if ASMAE surface is authority-eligible for state updates, prescriptions, and certification.
    
    V92.4-BC: Fail closed. Missing provenance fields are NOT defaulted to safe-looking
    values. Every check requires explicit proof to be present and correct.
    
    V92.4-BC.2: This is the AUTHORITY gate. Surfaces that fail this check can still
    render as diagnostic pixel overlays (if pixel_visual_eligible) or plot-level cards
    (if visual_eligible). Only state_update_allowed, prescription_driver_allowed,
    training_label_allowed, and certification depend on this gate.
    """
    prov = surface.provenance or {}
    
    # Grounding class check — UNIFORM/BROADCAST are never spatial
    gc = getattr(surface, "grounding_class", "UNIFORM") or "UNIFORM"
    if gc in ["UNIFORM", "BROADCAST"]:
        return False, "grounding_class_non_spatial"
    
    # Hard rejections for degraded states
    if prov.get("degraded_mean_only") is True:
        return False, "degraded_mean_only"
    if prov.get("no_scenes") is True:
        return False, "no_scenes"
    if prov.get("mean_only") is True:
        return False, "mean_only"
    
    # V92.4: Fail closed — require explicit spatial grid proof
    if prov.get("has_spatial_grid") is not True:
        return False, "no_spatial_grid"
    
    # V92.4: Fail closed — require scene stack to be real raster
    scene_stack_mode = prov.get("scene_stack_mode")
    if scene_stack_mode != "real_raster":
        return False, f"scene_stack_not_real_raster:{scene_stack_mode}"
    
    # V92.4: Fail closed — require operator and graph locks
    if prov.get("operator_locked") is not True:
        return False, "operator_not_locked"
    if prov.get("graph_locked") is not True:
        return False, "graph_not_locked"
    
    # V92.4-BC: Require exact ht_per_pixel radiometric mode — no boolean True
    radiometric_mode = prov.get("radiometric_mode")
    if radiometric_mode != "ht_per_pixel":
        return False, f"radiometric_not_ht_per_pixel:{radiometric_mode}"
    
    # V92.4-BC: Require full radiometric credit
    if prov.get("full_radiometric_credit_allowed") is not True:
        return False, "radiometric_credit_not_allowed"
    
    # V92.4-BC: Require exact ht_per_pixel EnKF mode — no boolean True
    enkf_mode = prov.get("enkf_mode")
    if enkf_mode != "ht_per_pixel":
        return False, f"enkf_not_ht_per_pixel:{enkf_mode}"
    
    # V92.4-BC: Require full EnKF credit
    if prov.get("full_enkf_credit_allowed") is not True:
        return False, "enkf_credit_not_allowed"
    
    # V92.4: Fail closed — reject proxy fallback
    if prov.get("has_enkf_proxy_fallback") is True:
        return False, "enkf_proxy_fallback"
    
    return True, "eligible"


def generate_asmae_aliases(
    H: int,
    W: int,
    surfaces: List[SurfaceArtifact],
    inp: Layer10Input,
    grid_spec_dict: Optional[dict] = None
) -> List[SurfaceArtifact]:
    """Generate canonical alias/proxy surfaces from ASMAE surfaces to bridge them to map modes.
    
    V92.4-BC.2: Uses three-tier eligibility:
      - visual_eligible: can be shown somewhere (card, badge, tint)
      - pixel_visual_eligible: can render as spatial pixel overlay
      - authority_eligible: can influence state/prescription/certification
    
    Aliases are generated when pixel_visual_eligible=True, even if authority_eligible=False.
    Authority-ineligible aliases get diagnostic_only=True and state_update_allowed=False.
    """
    aliases = []
    
    # Helper to find a surface by semantic type
    def has_exact_shape(surface: SurfaceArtifact) -> bool:
        try:
            _, height, width = _rectangular_grid(surface.values)
        except ValueError:
            return False
        return height == H and width == W

    def find_surf(stype: SurfaceType) -> Optional[SurfaceArtifact]:
        # Never trust an inherited grid_ref over the actual numeric array.
        return next(
            (s for s in surfaces if s.semantic_type == stype and has_exact_shape(s)),
            None,
        )

    # Alias mapping rules
    ASMAE_ALIAS_RULES = {
        SurfaceType.ASMAE_VIGOR: {
            "alias": SurfaceType.CANOPY_ASMAE_VIGOR,
            "mode": "canopy",
            "requires_spatial": True,
            "trust_label": "ASMAE vigor diagnostic",
            "warning": "ASMAE vigor diagnostic - not direct observation - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_CANOPY_WATER: {
            "alias": SurfaceType.WATER_ASMAE_CANOPY_WATER,
            "mode": "water",
            "requires_spatial": True,
            "trust_label": "ASMAE canopy water diagnostic",
            "warning": "Canopy water diagnostic, not confirmed water stress - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_ROOT_ZONE_WATER: {
            "alias": SurfaceType.WATER_ASMAE_ROOT_ZONE_WATER,
            "mode": "water",
            "requires_spatial": True,
            "trust_label": "ASMAE root-zone water estimate",
            "warning": "Root-zone water estimate, not confirmed water stress - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_CHLOROPHYLL: {
            "alias": SurfaceType.NUTRIENT_ASMAE_CHLOROPHYLL_PROXY,
            "mode": "nutrients",
            "requires_spatial": True,
            "trust_label": "ASMAE chlorophyll proxy",
            "warning": "Nutrient proxy from ASMAE chlorophyll - diagnostic only - confounded by water, salinity, disease, growth stage",
            "confounder_warnings": [
                "chlorophyll_proxy_not_confirmed_nutrient_stress",
                "confounded_by_water",
                "confounded_by_salinity",
                "confounded_by_biotic_stress",
                "confounded_by_crop_stage",
            ],
        },
        SurfaceType.ASMAE_SALINITY_STRESS: {
            "alias": SurfaceType.SALINITY_ASMAE_STRESS,
            "mode": "salinity",
            "requires_spatial": True,
            "trust_label": "ASMAE diagnostic salinity estimate",
            "warning": "ASMAE diagnostic salinity estimate - not direct observation - not prescription driver",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_EFFECTIVE_RESOLUTION: {
            "alias": SurfaceType.RESOLUTION_ASMAE_EFFECTIVE,
            "mode": "resolution",
            "requires_spatial": False,
            "trust_label": "ASMAE effective resolution",
            "warning": "ASMAE effective resolution diagnostic",
            "confounder_warnings": [],
        },
        # V92.4-BC.2: Veg attention separate aliases
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: {
            "alias": SurfaceType.VEG_ATTENTION_ASMAE_CONFLICT,
            "mode": "veg_attention",
            "requires_spatial": True,
            "trust_label": "ASMAE cross-layer conflict diagnostic",
            "warning": "ASMAE cross-layer conflict — diagnostic attention mask",
            "confounder_warnings": [],
        },
        SurfaceType.ASMAE_BMA_DISAGREEMENT: {
            "alias": SurfaceType.VEG_ATTENTION_ASMAE_DISAGREEMENT,
            "mode": "veg_attention",
            "requires_spatial": True,
            "trust_label": "ASMAE BMA disagreement diagnostic",
            "warning": "ASMAE model disagreement — diagnostic attention mask",
            "confounder_warnings": [],
        },
    }

    for src_type, rules in ASMAE_ALIAS_RULES.items():
        src_surf = find_surf(src_type)
        if not src_surf:
            continue
        
        # V92.4-BC.2: Three-tier eligibility
        visual_ok, visual_reason = asmae_surface_visual_eligible(src_surf)
        pixel_ok, pixel_reason = asmae_surface_pixel_visual_eligible(src_surf, output_grid_spec=grid_spec_dict)
        authority_ok, authority_reason = asmae_surface_spatially_eligible(src_surf)
        
        # If spatial display is required, need at least pixel_visual_eligible
        if rules["requires_spatial"] and not pixel_ok:
            continue
        
        # If not spatial but not visually eligible at all, skip
        if not rules["requires_spatial"] and not visual_ok:
            continue
            
        prov = dict(src_surf.provenance or {})
        prov.update({
            "alias_of": src_type.value,
            "map_mode": rules["mode"],
            "source_class": "asmae_diagnostic",
            "diagnostic_only": True,
            "direct_observation": False,
            "not_direct_observation": True,
            "management_zone_eligible": False,
            "prescription_driver_allowed": False,
            "state_update_allowed": False,
            "visual_only": False,
            "warning_wording": rules["warning"],
            # V92.4-BC.2: Full three-tier eligibility provenance
            "card_or_badge_eligible": visual_ok,
            "visual_eligibility_reason": visual_reason,
            "overlay_eligible": pixel_ok,
            "pixel_visual_reason": pixel_reason,
            "authority_eligible": authority_ok,
            "authority_block_reason": authority_reason if not authority_ok else None,
            "display_level": "asmae_diagnostic",
            "authority_level": "scout" if not authority_ok else "decision_support",
            "trust_badges": [
                "ASMAE diagnostic",
                "not direct observation",
                "not prescription driver",
            ],
        })
        
        # V92.4-BC.2: Confounder warnings for nutrient/chlorophyll proxy
        if rules.get("confounder_warnings"):
            prov["confounder_warnings"] = rules["confounder_warnings"]
        
        combined_blocks = resolve_surface_block_reasons(
            getattr(src_surf, "block_reasons", None),
            prov,
        )
        if combined_blocks:
            prov["block_reasons"] = list(combined_blocks)

        aliases.append(SurfaceArtifact(
            surface_id=f"{rules['alias'].value}_{inp.plot_id}",
            semantic_type=rules["alias"],
            grid_ref=src_surf.grid_ref,
            values=src_surf.values,
            units=src_surf.units,
            native_resolution_m=src_surf.native_resolution_m,
            render_range=src_surf.render_range,
            palette_id=src_surf.palette_id,
            source_layers=src_surf.source_layers,
            provenance=prov,
            state_update_allowed=bool(prov.get("state_update_allowed", False)),
            prescription_driver_allowed=bool(prov.get("prescription_driver_allowed", False)),
            grounding_class=src_surf.grounding_class,
            grid_spec=grid_spec_dict,
            source_grid_spec=src_surf.source_grid_spec,
            display_grid_spec=grid_spec_dict,
            block_reasons=list(combined_blocks) if combined_blocks else None,
        ))

    # ── V92.4-BC.2: VEG_ATTENTION_ASMAE_DIAGNOSTIC composite ──────────
    # Combines cross-layer conflict and BMA disagreement into a single
    # attention mask for farmer mode. Expert mode uses the separate aliases.
    veg_attn_ingredients = {
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: 0.45,
        SurfaceType.ASMAE_BMA_DISAGREEMENT: 0.35,
        SurfaceType.ASMAE_UNCERTAINTY: 0.20,
    }
    
    active_veg_ingredients = {}
    excluded_veg_ingredients = []
    for st, w in veg_attn_ingredients.items():
        s = find_surf(st)
        if s:
            is_bad, bad_reason = _is_surface_revoked_or_unsupported(s)
            if is_bad:
                excluded_veg_ingredients.append({"surface": st.value, "reason": bad_reason})
                continue
            pixel_ok, pixel_reason = asmae_surface_pixel_visual_eligible(s, output_grid_spec=grid_spec_dict)
            if pixel_ok:
                active_veg_ingredients[st] = (s, w)
            else:
                excluded_veg_ingredients.append({"surface": st.value, "reason": pixel_reason})
    
    if active_veg_ingredients:
        veg_attn_grid = [[None] * W for _ in range(H)]
        has_veg_val = False
        
        for r in range(H):
            for c in range(W):
                val_sum = 0.0
                weight_sum = 0.0
                for s, w in active_veg_ingredients.values():
                    v = s.values[r][c]
                    if v is not None:
                        val_sum += v * w
                        weight_sum += w
                
                if weight_sum > 0:
                    veg_attn_grid[r][c] = round(val_sum / weight_sum, 4)
                    has_veg_val = True
        
        if has_veg_val:
            res_m = next(iter(active_veg_ingredients.values()))[0].native_resolution_m
            
            aliases.append(SurfaceArtifact(
                surface_id=f"VEG_ATTENTION_ASMAE_DIAGNOSTIC_{inp.plot_id}",
                semantic_type=SurfaceType.VEG_ATTENTION_ASMAE_DIAGNOSTIC,
                grid_ref=f"{H}x{W}",
                values=veg_attn_grid,
                units="score",
                native_resolution_m=res_m,
                render_range=(0.0, 1.0),
                palette_id=PaletteId.RISK_HEAT,
                source_layers=["L1"],
                state_update_allowed=False,
                prescription_driver_allowed=False,
                provenance={
                    "alias_of": "ASMAE_VEG_ATTENTION_COMPOSITE",
                    "map_mode": "veg_attention",
                    "source_class": "asmae_diagnostic",
                    "diagnostic_only": True,
                    "not_direct_observation": True,
                    "prescription_driver_allowed": False,
                    "state_update_allowed": False,
                    "visual_only": False,
                    "has_spatial_grid": True,
                    "card_or_badge_eligible": True,
                    "overlay_eligible": True,
                    "authority_eligible": False,
                    "authority_block_reason": "diagnostic_composite",
                    "display_level": "asmae_diagnostic",
                    "authority_level": "scout",
                    "trust_badges": ["ASMAE diagnostic", "attention composite", "not prescription driver"],
                    "veg_attn_ingredients": [st.value for st in active_veg_ingredients.keys()],
                    "veg_attn_weights": {st.value: w for st, (_, w) in active_veg_ingredients.items()},
                    "excluded_ingredients": excluded_veg_ingredients,
                    "composite_method": "weighted_attention: 0.45 conflict + 0.35 disagreement + 0.20 uncertainty",
                    "warning_wording": "ASMAE diagnostic vegetation attention composite — not prescription driver.",
                },
                grounding_class=GroundingClass.RASTER_GROUNDED.value,
                grid_spec=grid_spec_dict,
            ))

    # ── RISK_ASMAE_DIAGNOSTIC: ASMAE diagnostic risk composite ────────
    risk_ingredients = {
        SurfaceType.ASMAE_BIOTIC_CONFOUNDER_RISK: 0.3,
        SurfaceType.ASMAE_THERMAL_STRESS: 0.2,
        SurfaceType.ASMAE_SALINITY_STRESS: 0.2,
        SurfaceType.ASMAE_BMA_DISAGREEMENT: 0.15,
        SurfaceType.ASMAE_CROSS_LAYER_CONFLICT: 0.15,
    }
    
    # S12-01 / S673-02: Filter risk ingredients on scientific support qualification and revocation
    active_ingredients = {}
    excluded_ingredients = []
    for st, w in risk_ingredients.items():
        s = find_surf(st)
        if s:
            is_bad, bad_reason = _is_surface_revoked_or_unsupported(s)
            if is_bad:
                excluded_ingredients.append({"surface": st.value, "reason": bad_reason})
                continue
            elig, elig_reason = asmae_surface_pixel_visual_eligible(s, output_grid_spec=grid_spec_dict)
            if elig:
                active_ingredients[st] = (s, w)
            else:
                excluded_ingredients.append({"surface": st.value, "reason": elig_reason})
            
    if active_ingredients:
        composite_grid = [[0.0] * W for _ in range(H)]
        has_val = False
        
        conf_surf = find_surf(SurfaceType.ASMAE_POSTERIOR_CONCENTRATION)
        retro_surf = find_surf(SurfaceType.ASMAE_RETROVALIDATION_SCORE)
        
        for r in range(H):
            for c in range(W):
                val_sum = 0.0
                weight_sum = 0.0
                for s, w in active_ingredients.values():
                    v = s.values[r][c]
                    if v is not None:
                        val_sum += v * w
                        weight_sum += w
                        
                if weight_sum > 0:
                    base_risk = val_sum / weight_sum
                    
                    # Apply trust weighting
                    conf_weight = conf_surf.values[r][c] if (conf_surf and conf_surf.values[r][c] is not None) else 0.8
                    retro_weight = retro_surf.values[r][c] if (retro_surf and retro_surf.values[r][c] is not None) else 0.85
                    
                    composite_grid[r][c] = round(base_risk * conf_weight * retro_weight, 4)
                    has_val = True
                else:
                    composite_grid[r][c] = None
                    
        if has_val:
            res_m = next(iter(active_ingredients.values()))[0].native_resolution_m
            
            # V92.4-BC.2: Risk authority is diagnostic_only unless every primary ingredient is authority-eligible
            risk_authority_ok = all(
                asmae_surface_spatially_eligible(s)[0]
                for s, _ in active_ingredients.values()
            )
            
            aliases.append(SurfaceArtifact(
                surface_id=f"RISK_ASMAE_DIAGNOSTIC_{inp.plot_id}",
                semantic_type=SurfaceType.RISK_ASMAE_DIAGNOSTIC,
                grid_ref=f"{H}x{W}",
                values=composite_grid,
                units="score",
                native_resolution_m=res_m,
                render_range=(0.0, 1.0),
                palette_id=PaletteId.RISK_HEAT,
                source_layers=["L1"],
                state_update_allowed=False,
                prescription_driver_allowed=False,
                provenance={
                    "alias_of": "ASMAE_RISK_COMPOSITE",
                    "map_mode": "composite_risk",
                    "source_class": "asmae_diagnostic",
                    "diagnostic_only": True,
                    "not_direct_observation": True,
                    "prescription_driver_allowed": False,
                    "state_update_allowed": False,
                    "visual_only": False,
                    "has_spatial_grid": True,
                    "card_or_badge_eligible": True,
                    "overlay_eligible": True,
                    "authority_eligible": risk_authority_ok,
                    "authority_block_reason": "diagnostic_composite" if not risk_authority_ok else None,
                    "display_level": "asmae_diagnostic",
                    "authority_level": "decision_support" if risk_authority_ok else "scout",
                    "trust_badges": ["ASMAE diagnostic", "not prescription driver"],
                    "risk_ingredients": [st.value for st in active_ingredients.keys()],
                    "excluded_ingredients": excluded_ingredients,
                    "composite_method": "weighted_diagnostic",
                    "warning_wording": "ASMAE diagnostic risk composite — not prescription driver.",
                },
                grounding_class=GroundingClass.RASTER_GROUNDED.value,
                grid_spec=grid_spec_dict,
            ))

    # Compatibility names resolve to this canonical surface in metadata.  Do
    # not publish a second numeric grid: duplicated arrays can diverge while
    # appearing to describe the same scientific quantity.
    conf_surf = find_surf(SurfaceType.ASMAE_POSTERIOR_CONCENTRATION)
    if conf_surf:
        conf_surf.provenance = {
            **(conf_surf.provenance or {}),
            "compatibility_aliases": ["ASMAE_CONFIDENCE", "CONFIDENCE_ASMAE"],
        }

    return aliases

