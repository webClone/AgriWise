import os
import glob
import json
import hashlib
import logging
from datetime import datetime, date, timedelta, timezone
import numpy as np
import requests
from .scene_product_schema import SceneProduct
from .scene_product_store import SceneProductStore
from services.agribrain.layer0.native_issuer.acquisition_evidence import (
    capture_backend_provider_response, NativeEvidenceError,
)
from .product_binding import (
    exact_binding_proof_valid,
    verify_exact_product_binding,
)
from eo.sentinel import get_access_token, SENTINEL_PROCESS_URL

logger = logging.getLogger(__name__)


def _request_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _retry_class(reason: str) -> str:
    if reason in {"credentials_missing", "authentication_failed"}:
        return "credentials"
    if reason in {"no_geometry", "invalid_request", "missing_metadata"}:
        return "request_contract"
    if reason == "no_scene_found":
        return "no_data"
    if reason in {"provider_timeout", "rate_limited", "provider_error"}:
        return "transient"
    return "permanent"


def _unavailable(stage: str, reason: str, date_range: tuple, *, accepted_count: int = 0, candidate_count: int = 0, http_status: int = 0, request_id: str = "") -> dict:
    start, end = date_range
    return {
        "status": "unavailable",
        "reason": reason,
        "real_scene_count": accepted_count,
        "provider_attempt": {
            "provider": "sentinel_hub", "sensor": "S1", "stage": stage,
            "request_id": request_id, "http_status": int(http_status or 0),
            "provider_error_code": reason,
            "retry_classification": _retry_class(reason),
            "candidate_count": int(candidate_count), "accepted_count": int(accepted_count),
            "rejection_reasons": [reason] if reason else [],
            "geometry_hash": "",
            "time_window": [str(start), str(end)],
        },
    }


def _stable_array_hash(bands: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in sorted(bands):
        array = np.ascontiguousarray(np.asarray(bands[name]))
        digest.update(name.encode("ascii"))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _has_complete_s1_orbit_metadata(metadata: dict) -> bool:
    """Return whether cached provider metadata can support crop independence.

    Older raster artifacts remain useful to ASMAE, but artifacts written
    before orbit metadata was persisted cannot become independent crop
    evidence.  This check is intentionally limited to refresh planning; the
    canonical crop observation resolver remains the scientific authority.
    """
    records = []
    pending = [metadata]
    seen = set()
    while pending:
        current = pending.pop(0)
        if isinstance(current, dict):
            marker = id(current)
            if marker in seen:
                continue
            seen.add(marker)
            records.append(current)
            for key in (
                "process_metadata", "process_api_metadata", "userData",
                "userdata", "tiles", "catalog_metadata", "properties",
                "stac_metadata", "official_product_identity",
            ):
                nested = current.get(key)
                if isinstance(nested, (dict, list, tuple)):
                    pending.append(nested)
        elif isinstance(current, (list, tuple)):
            pending.extend(current)

    relative = None
    direction = None
    relative_aliases = (
        "provider_relative_orbit", "process_relative_orbit",
        "relative_orbit", "relative_orbit_number", "relativeOrbitNumber",
        "sat:relative_orbit", "s1:relative_orbit",
    )
    direction_aliases = (
        "provider_orbit_pass", "orbit_pass", "orbit_direction",
        "orbitDirection", "orbitPass", "sat:orbit_state", "s1:orbit_state",
    )
    for record in records:
        if relative is None:
            for alias in relative_aliases:
                raw = str(record.get(alias) or "").strip().upper()
                if raw.startswith("R"):
                    raw = raw[1:]
                if raw.isdigit() and 1 <= int(raw) <= 175:
                    relative = int(raw)
                    break
        if direction is None:
            for alias in direction_aliases:
                raw = str(record.get(alias) or "").strip().upper()
                normalized = {
                    "A": "ASCENDING", "ASC": "ASCENDING",
                    "D": "DESCENDING", "DES": "DESCENDING",
                    "DESC": "DESCENDING",
                }.get(raw, raw)
                if normalized in {"ASCENDING", "DESCENDING"}:
                    direction = normalized
                    break
        if relative is not None and direction is not None:
            return True
    return False

def fetch_asmae_s1_scene_stack(
    plot_id: str,
    run_id: str,
    date_range: tuple,
    raster_composites: dict,
    lat: float = None,
    lng: float = None,
    polygon_coords: list = None
) -> list[SceneProduct] | dict:
    """
    Fetches real Sentinel-1 scene stack.
    1. If ASMAE_TEST_OVERRIDE is active, generates mock Sentinel-1 scenes with test override provenance.
    2. Otherwise, checks local artifacts/real_scenes/{plot_id}_{run_id} folder for real-scene fixtures.
       Validates strict metadata contract. Fail closed on corrupt/missing data.
    3. If local fixtures are absent, queries Sentinel Hub Process API using existing credentials.
    4. If both fail, returns structured fail-closed telemetry with exact error reason.
    """
    test_override = os.environ.get("ASMAE_TEST_OVERRIDE", "false").lower() == "true"
    
    # ── 1. TEST OVERRIDE WORKFLOW ──
    if test_override:
        start_date, end_date = date_range
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
            
        sar_data = raster_composites.get("SAR") or {}
        pixel_array = sar_data.get("values") or sar_data.get("pixel_array")
        
        if not (pixel_array and len(pixel_array) > 0 and len(pixel_array[0]) > 0):
            ndvi_data = raster_composites.get("NDVI") or raster_composites.get("NDVI_CLEAN") or {}
            pixel_array = ndvi_data.get("values") or ndvi_data.get("pixel_array")
            
        if pixel_array and len(pixel_array) > 0 and len(pixel_array[0]) > 0:
            H = len(pixel_array)
            W = len(pixel_array[0])
            grid_spec = sar_data.get("grid_spec") or (raster_composites.get("NDVI") or {}).get("grid_spec") or {}
        else:
            H, W = 8, 8
            pixel_array = [[0.2] * W for _ in range(H)]
            grid_spec = {
                "crs": "EPSG:4326",
                "transform": (0.0, 10.0, 0.0, 0.0, 0.0, -10.0),
            }
            
        crs = grid_spec.get("crs", "EPSG:4326")
        transform = grid_spec.get("transform", (0.0, 10.0, 0.0, 0.0, 0.0, -10.0))
        if isinstance(transform, list):
            transform = tuple(transform)
            
        sar_arr = np.array(pixel_array, dtype=np.float32)
        vv_arr = sar_arr
        vh_arr = None
        vh_data = raster_composites.get("VH") or raster_composites.get("SAR_VH") or {}
        vh_pixel = vh_data.get("values") or vh_data.get("pixel_array")
        if (vh_pixel and isinstance(vh_pixel, list)
                and len(vh_pixel) == H and isinstance(vh_pixel[0], list)
                and len(vh_pixel[0]) == W):
            vh_arr = np.array(vh_pixel, dtype=np.float32)
            
        store = SceneProductStore(plot_id, run_id)
        end_dt = datetime.combine(end_date, datetime.min.time(), timezone.utc)
        
        scenes = []
        for i in range(1, 3):
            scene_id = f"s1_real_scene_{i}_{plot_id}"
            acq_dt = end_dt - timedelta(days=8 - 5 * (i - 1))
            
            band_refs = {}
            bands_to_save = {
                "VV": vv_arr,
            }
            if vh_arr is not None:
                bands_to_save["VH"] = vh_arr
            
            for b_name, arr in bands_to_save.items():
                path = store.save_band(scene_id, b_name, arr)
                band_refs[b_name] = path
                
            scenes.append(SceneProduct(
                scene_id=scene_id,
                sensor="S1",
                acquisition_datetime=acq_dt,
                crs=crs,
                transform=transform,
                width=W,
                height=H,
                band_refs=band_refs,
                mask_refs={},
                band_units={"VV": "linear_power", "VH": "linear_power"},
                quality={
                    "valid_fraction": 1.0,
                },
                source_reality="test_fixture_raster",
                test_override=True,
                production_usable=False,
                real_provider_product=False,
                usable_for_1m_approval=False,
                usable_for_advisory=False,      # blocked unless ASMAE_DEV_MODE
                diagnostic_only=True,
                excluded_from_archive_metrics=True,
                excluded_from_retrovalidation_holdouts=True,
                excluded_from_bma_holdout_performance=True
            ))
        return scenes

    # ── 2. LOCAL FIXTURE WORKFLOW ──
    # General store under plot_id to scan files
    store = SceneProductStore(plot_id, run_id)
    base_dir = store.base_dir
    metadata_files = []
    
    # 1. Recursive scan under artifacts/real_scenes/{plot_id}/
    if os.path.exists(base_dir):
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file == "metadata.json" or (file.startswith("s1_real_scene_") and file.endswith("_metadata.json")):
                    metadata_files.append(os.path.join(root, file))
                    
    # 2. Backward compatibility: artifacts/real_scenes/{plot_id}_{run_id}
    legacy_base_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "artifacts",
        "real_scenes",
        f"{plot_id}_{run_id}"
    ))
    if os.path.exists(legacy_base_dir):
        for root, dirs, files in os.walk(legacy_base_dir):
            for file in files:
                if file == "metadata.json" or (file.startswith("s1_real_scene_") and file.endswith("_metadata.json")):
                    metadata_files.append(os.path.join(root, file))

    seen_ids = set()
    seen_content_hashes: dict[str, str] = {}
    local_scenes = []
    cached_by_provider_id = {}
    orbit_complete_provider_ids = set()
    failed_closed = False
    fail_reason = None
    
    start_date, end_date = date_range
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)
        
    start_dt = datetime.combine(start_date, datetime.min.time(), timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), timezone.utc)
    from .geometry_utils import extract_polygon_ring, _build_affine_transform
    field_ring = extract_polygon_ring(polygon_coords)

    for mf in metadata_files:
        try:
            with open(mf, "r") as f:
                meta = json.load(f)

            provider_hint = str(
                meta.get("provider_product_id") or meta.get("scene_id") or ""
            ).upper()
            sensor_hint = str(meta.get("sensor") or "").upper()
            if sensor_hint and sensor_hint != "S1":
                continue
            if not sensor_hint and not provider_hint.startswith("S1"):
                continue
            
            scene_id = meta.get("scene_id")
            prov_prod_id = meta.get("provider_product_id") or scene_id
            if not scene_id or prov_prod_id in seen_ids:
                continue
                
            # Filter by date range
            acq_time_str = meta.get("acquisition_datetime")
            if not acq_time_str:
                continue
            acq_dt = datetime.fromisoformat(acq_time_str.replace("Z", "+00:00"))
            if not (start_dt <= acq_dt <= end_dt):
                continue
                
            # Verify strict local metadata contract
            required_fields = ["scene_id", "acquisition_datetime", "crs", "transform", "width", "height", "source_reality"]
            if not all(k in meta for k in required_fields):
                failed_closed = True
                fail_reason = "missing_metadata"
                break
            
            if meta["source_reality"] != "real_raster":
                failed_closed = True
                fail_reason = "invalid_source_reality"
                break
                
            if not isinstance(meta["transform"], (list, tuple)) or len(meta["transform"]) != 6:
                failed_closed = True
                fail_reason = "invalid_transform"
                break
            
            scene_dir = os.path.dirname(mf)
            
            # Locate bands in the directory
            vv_path = os.path.join(scene_dir, "VV.npz")
            if not os.path.exists(vv_path):
                vv_path = os.path.join(scene_dir, f"{scene_id}_VV.npz")
                
            vh_path = os.path.join(scene_dir, "VH.npz")
            if not os.path.exists(vh_path):
                vh_path = os.path.join(scene_dir, f"{scene_id}_VH.npz")

            dm_path = os.path.join(scene_dir, "DATAMASK.npz")
            if not os.path.exists(dm_path):
                dm_path = os.path.join(scene_dir, "dataMask.npz")
                
            if not os.path.exists(vv_path) and not os.path.exists(vh_path):
                failed_closed = True
                fail_reason = "missing_VV_VH"
                break
            
            # Check loading
            band_refs = {}
            content_bands = {}
            try:
                if os.path.exists(vv_path):
                    content_bands["VV"] = np.asarray(store.raster_store.load_band(vv_path))
                    band_refs["VV"] = vv_path
                if os.path.exists(vh_path):
                    content_bands["VH"] = np.asarray(store.raster_store.load_band(vh_path))
                    band_refs["VH"] = vh_path
                mask_refs = {}
                if os.path.exists(dm_path):
                    store.raster_store.load_band(dm_path)
                    mask_refs["dataMask"] = dm_path
            except Exception:
                failed_closed = True
                fail_reason = "corrupted_band"
                break

            content_hash = _stable_array_hash(content_bands)
            duplicate_of = seen_content_hashes.get(content_hash)
            if duplicate_of:
                logger.warning(
                    "Quarantining duplicate S1 raster content: scene=%s duplicate_of=%s hash=%s",
                    scene_id, duplicate_of, content_hash,
                )
                continue
            seen_content_hashes[content_hash] = scene_id
            cached_exact = bool(
                meta.get("product_binding") == "exact_catalog_item"
                and exact_binding_proof_valid(
                    prov_prod_id, meta.get("binding_proof"),
                )
            )
            
            # Verify scene spatial extent covers the plot envelope
            if field_ring and len(field_ring) >= 3:
                p_xs = [float(p[0]) for p in field_ring]
                p_ys = [float(p[1]) for p in field_ring]
                plot_min_x, plot_max_x = min(p_xs), max(p_xs)
                plot_min_y, plot_max_y = min(p_ys), max(p_ys)

                t = meta.get("transform")
                w, h = meta.get("width", 0), meta.get("height", 0)
                if meta.get("bounds"):
                    s_min_x, s_min_y, s_max_x, s_max_y = meta["bounds"]
                elif t and len(t) == 6 and w > 0 and h > 0:
                    s_min_x = min(t[0], t[0] + w * t[1])
                    s_max_x = max(t[0], t[0] + w * t[1])
                    s_min_y = min(t[3], t[3] + h * t[5])
                    s_max_y = max(t[3], t[3] + h * t[5])
                else:
                    s_min_x = s_max_x = s_min_y = s_max_y = None

                if s_min_x is not None:
                    # If cached scene does not cover plot envelope (with 1e-4 tolerance), skip it
                    if (s_min_x > plot_min_x + 1e-4 or s_max_x < plot_max_x - 1e-4 or
                        s_min_y > plot_min_y + 1e-4 or s_max_y < plot_max_y - 1e-4):
                        logger.warning(
                            "Skipping cached S1 scene %s: extent does not cover plot envelope (scene=[%.6f, %.6f, %.6f, %.6f] vs plot=[%.6f, %.6f, %.6f, %.6f])",
                            scene_id, s_min_x, s_min_y, s_max_x, s_max_y, plot_min_x, plot_min_y, plot_max_x, plot_max_y,
                        )
                        continue

            seen_ids.add(prov_prod_id)
            sp = SceneProduct(
                scene_id=scene_id,
                sensor="S1",
                acquisition_datetime=acq_dt,
                crs=meta["crs"],
                transform=tuple(meta["transform"]),
                width=meta["width"],
                height=meta["height"],
                band_refs=band_refs,
                mask_refs=mask_refs,
                band_units=dict(meta.get("band_units") or {
                    "VV": "linear_power", "VH": "linear_power",
                }),
                quality=meta.get("quality", {"valid_fraction": 1.0}),
                source_reality="real_raster",
                test_override=False,
                production_usable=cached_exact,
                diagnostic_only=not cached_exact,
                real_provider_product=cached_exact,
                usable_for_1m_approval=cached_exact,
                usable_for_advisory=cached_exact,
                provider_product_id=prov_prod_id,
                catalog_item_id=meta.get("catalog_item_id") or prov_prod_id,
                provider_tile_id=meta.get("provider_tile_id"),
                provider_orbit_id=meta.get("provider_orbit_id"),
                provider_orbit_pass=meta.get("provider_orbit_pass"),
                provider_relative_orbit=meta.get("provider_relative_orbit"),
                provider_absolute_orbit=meta.get("provider_absolute_orbit"),
                process_metadata=dict(meta.get("process_metadata") or {}),
                catalog_metadata=dict(meta.get("catalog_metadata") or {}),
                content_hash=content_hash,
                process_request_hash=meta.get("process_request_hash"),
                provider_response_hash=meta.get("provider_response_hash"),
                product_binding=meta.get("product_binding", "legacy_unproven"),
                binding_proof=dict(meta.get("binding_proof") or {}),
            )
            local_scenes.append(sp)
            if _has_complete_s1_orbit_metadata(meta):
                cached_by_provider_id[prov_prod_id] = sp
                orbit_complete_provider_ids.add(prov_prod_id)
        except Exception:
            failed_closed = True
            fail_reason = "provider_error"
            break
            
    if failed_closed:
        return _unavailable("scene_validation", fail_reason or "provider_error", date_range)
    if len(local_scenes) >= 2 and len(orbit_complete_provider_ids) >= 2:
        return local_scenes

    # ── 3. SENTINEL HUB PROCESS API FALLBACK ──
    client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        if local_scenes:
            return local_scenes
        return _unavailable("authentication", "credentials_missing", date_range, accepted_count=len(local_scenes))

    # Construct bbox/geometry in WGS84 for STAC search
    sar_data = raster_composites.get("SAR") or {}
    ndvi_data = raster_composites.get("NDVI") or raster_composites.get("NDVI_CLEAN") or {}
    grid_spec = sar_data.get("grid_spec") or ndvi_data.get("grid_spec") or {}
    if not grid_spec and "NDVI_CLEAN" in raster_composites:
        grid_spec = raster_composites["NDVI_CLEAN"].get("grid_spec") or {}

    grid_bounds = grid_spec.get("bounds") or grid_spec.get("bbox")
    ring = field_ring

    if grid_bounds and len(grid_bounds) >= 4:
        bbox = [float(v) for v in grid_bounds]
    elif ring:
        try:
            xs = [float(p[0]) for p in ring]
            ys = [float(p[1]) for p in ring]
            pad_x = max((max(xs) - min(xs)) * 0.05, 0.0002)
            pad_y = max((max(ys) - min(ys)) * 0.05, 0.0002)
            bbox = [min(xs) - pad_x, min(ys) - pad_y, max(xs) + pad_x, max(ys) + pad_y]
        except Exception:
            if local_scenes:
                return local_scenes
            return _unavailable("request_build", "no_geometry", date_range, accepted_count=len(local_scenes))
    elif lat is not None and lng is not None:
        buffer = 0.003
        bbox = [lng - buffer, lat - buffer, lng + buffer, lat + buffer]
    else:
        if local_scenes:
            return local_scenes
        return _unavailable("request_build", "no_geometry", date_range, accepted_count=len(local_scenes))
        
    crs = grid_spec.get("crs", "EPSG:4326")
    transform = grid_spec.get("transform")
    
    pixel_array = sar_data.get("values") or sar_data.get("pixel_array") or ndvi_data.get("values") or ndvi_data.get("pixel_array")
    if pixel_array and len(pixel_array) > 0 and len(pixel_array[0]) > 0:
        H = len(pixel_array)
        W = len(pixel_array[0])
    elif "width" in grid_spec and "height" in grid_spec:
        W = int(grid_spec["width"])
        H = int(grid_spec["height"])
    else:
        lon_span = bbox[2] - bbox[0]
        lat_span = bbox[3] - bbox[1]
        W = max(8, int(round(lon_span / 0.0001)))
        H = max(8, int(round(lat_span / 0.0001)))

    if not transform or not isinstance(transform, (list, tuple)) or len(transform) != 6:
        try:
            transform = _build_affine_transform(bbox, W, H)
        except ValueError:
            if local_scenes:
                return local_scenes
            return _unavailable(
                "request_build", "no_geometry", date_range,
                accepted_count=len(local_scenes),
            )
            lon_step = (bbox[2] - bbox[0]) / max(1, W)
            lat_step = (bbox[3] - bbox[1]) / max(1, H)
            transform = (bbox[0], lon_step, 0.0, bbox[3], 0.0, -lat_step)
        
    try:
        token = get_access_token()
    except Exception:
        if local_scenes:
            return local_scenes
        return _unavailable("authentication", "credentials_missing", date_range, accepted_count=len(local_scenes))
        
    stac_url = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
    start_date, end_date = date_range
    if not isinstance(start_date, str):
        start_date = start_date.strftime("%Y-%m-%d")
    if not isinstance(end_date, str):
        end_date = end_date.strftime("%Y-%m-%d")
        
    stac_payload = {
        "bbox": bbox,
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "collections": ["sentinel-1-grd"],
        "limit": 15
    }
    
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(stac_url, json=stac_payload, headers=headers, timeout=25)
        if resp.status_code != 200:
            if local_scenes:
                return local_scenes
            reason = "rate_limited" if resp.status_code == 429 else "provider_error"
            return _unavailable("catalog_query", reason, date_range, accepted_count=len(local_scenes), http_status=resp.status_code, request_id=resp.headers.get("x-request-id", ""))
        catalog_acquisition = capture_backend_provider_response(
            response=resp, endpoint=stac_url, request_parameters=stac_payload,
            sensor="S1",
        )
        features = resp.json().get("features", [])
    except NativeEvidenceError:
        return _unavailable("acquisition_evidence", "untrusted_native_capture", date_range)
    except Exception:
        if local_scenes:
            return local_scenes
        return _unavailable("catalog_query", "provider_error", date_range, accepted_count=len(local_scenes))
        
    if not features and not local_scenes:
        return _unavailable("catalog_query", "no_scene_found", date_range)
        
    # Select up to 4 scenes to fetch
    selected_features = features[:4]
    
    evalscript_template = """
    //VERSION=3
    const EXPECTED_PRODUCT_ID = __EXPECTED_PRODUCT_ID__;
    function normalizeProductId(value) {
        return String(value || "").toUpperCase().replace(".SAFE", "").replace(".ZIP", "");
    }
    function tileProductId(tile) {
        return tile.sentinel1ProductId || tile.productId || tile.id || "";
    }
    function setup() {
        return {
            input: [{bands: ["VV", "VH", "dataMask"]}],
            output: [
                {id: "VV", bands: 1, sampleType: "FLOAT32"},
                {id: "VH", bands: 1, sampleType: "FLOAT32"},
                {id: "dataMask", bands: 1, sampleType: "UINT8"}
            ],
            mosaicking: "TILE"
        };
    }
    function preProcessScenes(collections) {
        const tiles = (collections.scenes && collections.scenes.tiles) || [];
        collections.scenes.tiles = tiles.filter(function(tile) {
            return normalizeProductId(tileProductId(tile)) === normalizeProductId(EXPECTED_PRODUCT_ID);
        });
        return collections;
    }
    function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
        const tiles = (scenes && scenes.tiles) || [];
        outputMetadata.userData = {
            expectedProductId: EXPECTED_PRODUCT_ID,
            tiles: tiles.map(function(tile) {
                return {
                    sentinel1ProductId: tile.sentinel1ProductId,
                    productId: tile.productId,
                    id: tile.id,
                    tileId: tile.tileId,
                    shId: tile.shId,
                    dataPath: tile.dataPath,
                    date: tile.date,
                    orbitId: tile.orbitId,
                    relativeOrbitNumber: tile.relativeOrbitNumber,
                    orbitDirection: tile.orbitDirection
                };
            })
        };
    }
    function value(sample, name, fallback) {
        return sample && sample[name] !== undefined ? sample[name] : fallback;
    }
    function evaluatePixel(samples) {
        const sample = samples && samples.length ? samples[0] : null;
        return {
            VV: [value(sample, "VV", NaN)],
            VH: [value(sample, "VH", NaN)],
            dataMask: [value(sample, "dataMask", 0)]
        };
    }
    """
    
    fetched_scenes = []
    for idx, f in enumerate(selected_features, 1):
        props = f.get("properties", {})
        acq_time_str = props.get("datetime")
        acq_dt = datetime.fromisoformat(acq_time_str.replace("Z", "+00:00"))
        scene_date_str = acq_dt.strftime("%Y-%m-%d")
        provider_product_id = f.get("id", f"S1_{scene_date_str}")
        scene_id = f"s1_real_scene_{idx}_{plot_id}"
        evalscript = evalscript_template.replace(
            "__EXPECTED_PRODUCT_ID__", json.dumps(provider_product_id),
        )
        request_start = (acq_dt - timedelta(minutes=5)).astimezone(
            timezone.utc,
        ).isoformat().replace("+00:00", "Z")
        request_end = (acq_dt + timedelta(minutes=5)).astimezone(
            timezone.utc,
        ).isoformat().replace("+00:00", "Z")
        
        # Check if already cached!
        if provider_product_id in cached_by_provider_id:
            logger.info("Using cached S1 scene in Process API loop: %s", provider_product_id)
            fetched_scenes.append(cached_by_provider_id[provider_product_id])
            continue
            
        # Call Process API
        bounds_payload = {
            "bbox": bbox,
            "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
        }
        process_payload = {
            "input": {
                "bounds": bounds_payload,
                "data": [{
                    "type": "sentinel-1-grd",
                    "dataFilter": {"mosaickingOrder": "mostRecent"},
                    "timeRange": {"from": request_start, "to": request_end}
                }]
            },
            "output": {
                "width": W,
                "height": H,
                "responses": [
                    {"identifier": b, "format": {"type": "image/tiff"}}
                    for b in ["VV", "VH", "dataMask"]
                ] + [
                    {"identifier": "userdata", "format": {"type": "application/json"}}
                ]
            },
            "evalscript": evalscript,
        }
        process_request_hash = _request_hash(process_payload)
        
        try:
            p_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/tar"}
            p_resp = requests.post(SENTINEL_PROCESS_URL, json=process_payload, headers=p_headers, timeout=30)
            if p_resp.status_code != 200:
                if local_scenes:
                    continue
                reason = "rate_limited" if p_resp.status_code == 429 else "provider_error"
                return _unavailable("process_api", reason, date_range, accepted_count=len(fetched_scenes), candidate_count=len(selected_features), http_status=p_resp.status_code, request_id=p_resp.headers.get("x-request-id", ""))
            
            # B2B-01: record the exact successful backend Process response
            # before decoding bands. This is NOT QA or issuer authorization.
            process_acquisition = capture_backend_provider_response(
                response=p_resp, endpoint=SENTINEL_PROCESS_URL,
                request_parameters=process_payload, sensor="S1",
                provider_product_id=provider_product_id,
            )

            # Parse tar
            import io
            import tarfile
            try:
                import tifffile
            except ImportError:
                if local_scenes:
                    continue
                return _unavailable("decode", "provider_error", date_range, accepted_count=len(fetched_scenes), candidate_count=len(selected_features))
                
            bands_data = {}
            process_userdata = {}
            with tarfile.open(fileobj=io.BytesIO(p_resp.content)) as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.lower().endswith((".tif", ".tiff")):
                        name = member.name.split(".")[0].upper()
                        f_extracted = tar.extractfile(member)
                        if f_extracted:
                            with tifffile.TiffFile(io.BytesIO(f_extracted.read())) as tif:
                                bands_data[name] = tif.asarray()
                    elif member.isfile() and member.name.lower().endswith(".json"):
                        f_extracted = tar.extractfile(member)
                        if f_extracted:
                            try:
                                process_userdata = json.loads(
                                    f_extracted.read().decode("utf-8"),
                                )
                            except (UnicodeDecodeError, json.JSONDecodeError):
                                process_userdata = {}
                                
            # Ensure minimum bands are loaded
            if "VV" not in bands_data and "VH" not in bands_data:
                if local_scenes:
                    continue
                return _unavailable("scene_validation", "missing_VV_VH", date_range, accepted_count=len(fetched_scenes), candidate_count=len(selected_features))

            binding = verify_exact_product_binding(
                provider_product_id, process_userdata, "S1",
            )
            exact_binding = binding["is_exact"]

            content_bands = {
                name: np.asarray(array)
                for name, array in bands_data.items()
                if name in {"VV", "VH", "DATAMASK"}
            }
            content_hash = _stable_array_hash(content_bands)
            if content_hash in seen_content_hashes:
                logger.warning(
                    "Quarantining Process API duplicate S1 content: catalog_selection=%s duplicate_of=%s hash=%s",
                    provider_product_id, seen_content_hashes[content_hash], content_hash,
                )
                continue
            seen_content_hashes[content_hash] = scene_id
            provider_response_hash = hashlib.sha256(p_resp.content).hexdigest()
            valid_anchor = bands_data.get("VV")
            if valid_anchor is None:
                valid_anchor = bands_data.get("VH")
            valid = np.isfinite(np.asarray(valid_anchor))
            if "DATAMASK" in bands_data:
                valid &= np.asarray(bands_data["DATAMASK"]) > 0
            valid_fraction = float(np.count_nonzero(valid) / valid.size) if valid.size else 0.0
                
            # Save bands to NPZ files inside the provider-specific folder
            scene_store = SceneProductStore(plot_id, run_id, provider_product_id=provider_product_id)
            band_refs = {}
            for b_name, arr in bands_data.items():
                path = scene_store.save_band(scene_id, b_name, arr)
                band_refs[b_name] = path
            mask_refs = {}
            if "DATAMASK" in band_refs:
                mask_refs["DATAMASK"] = band_refs.pop("DATAMASK")
                
            # Write metadata.json in that provider subfolder
            metadata = {
                "scene_id": scene_id,
                "acquisition_datetime": acq_dt.isoformat(),
                "crs": crs,
                "transform": list(transform),
                "width": W,
                "height": H,
                "provider_product_id": provider_product_id,
                "catalog_item_id": provider_product_id,
                "provider_tile_id": binding.get("provider_tile_id"),
                "provider_orbit_id": binding.get("provider_orbit_id"),
                "provider_orbit_pass": binding.get("provider_orbit_pass"),
                "provider_relative_orbit": binding.get("provider_relative_orbit"),
                "provider_absolute_orbit": binding.get("provider_absolute_orbit"),
                "process_metadata": binding.get("process_metadata") or {},
                "catalog_metadata": dict(props),
                "source_reality": "real_raster",
                "production_usable": exact_binding,
                "diagnostic_only": not exact_binding,
                "real_provider_product": exact_binding,
                "product_binding": binding["product_binding"],
                "binding_proof": binding["proof"],
                "catalog_selection_id": provider_product_id,
                "process_request_hash": process_request_hash,
                "provider_response_hash": provider_response_hash,
                "native_catalog_acquisition_id": (
                    catalog_acquisition.acquisition_id if catalog_acquisition else None
                ),
                "native_process_acquisition_id": (
                    process_acquisition.acquisition_id if process_acquisition else None
                ),
                "native_evidence_status": "CAPTURED_UNQUALIFIED" if process_acquisition else "UNATTESTED",
                "content_hash": content_hash,
                "quality": {
                    "valid_fraction": valid_fraction
                },
                "band_units": {"VV": "linear_power", "VH": "linear_power"},
                "first_seen_run_id": run_id,
                "last_used_run_id": run_id
            }
            meta_path = os.path.join(scene_store.base_dir, "metadata.json")
            with open(meta_path, "w") as f_meta:
                json.dump(metadata, f_meta, indent=2)
                
            fetched_scenes.append(SceneProduct(
                scene_id=scene_id,
                sensor="S1",
                acquisition_datetime=acq_dt,
                crs=crs,
                transform=tuple(transform),
                width=W,
                height=H,
                band_refs=band_refs,
                mask_refs=mask_refs,
                band_units={"VV": "linear_power", "VH": "linear_power"},
                quality=metadata["quality"],
                source_reality="real_raster",
                test_override=False,
                production_usable=exact_binding,
                diagnostic_only=not exact_binding,
                real_provider_product=exact_binding,
                usable_for_1m_approval=exact_binding,
                usable_for_advisory=exact_binding,
                provider_product_id=provider_product_id,
                catalog_item_id=provider_product_id,
                provider_tile_id=binding.get("provider_tile_id"),
                provider_orbit_id=binding.get("provider_orbit_id"),
                provider_orbit_pass=binding.get("provider_orbit_pass"),
                provider_relative_orbit=binding.get("provider_relative_orbit"),
                provider_absolute_orbit=binding.get("provider_absolute_orbit"),
                process_metadata=dict(binding.get("process_metadata") or {}),
                catalog_metadata=dict(props),
                content_hash=content_hash,
                process_request_hash=process_request_hash,
                native_catalog_acquisition_id=(
                    catalog_acquisition.acquisition_id if catalog_acquisition else None
                ),
                native_process_acquisition_id=(
                    process_acquisition.acquisition_id if process_acquisition else None
                ),
                native_evidence_status="CAPTURED_UNQUALIFIED" if process_acquisition else "UNATTESTED",
                provider_response_hash=metadata["provider_response_hash"],
                product_binding=binding["product_binding"],
                binding_proof=binding["proof"],
            ))
        except NativeEvidenceError:
            logger.error("Native S1 acquisition evidence capture failed closed")
            return _unavailable("acquisition_evidence", "untrusted_native_capture", date_range)
        except Exception:
            if local_scenes:
                continue
            return _unavailable("decode", "provider_error", date_range, accepted_count=len(fetched_scenes), candidate_count=len(selected_features))
            
    # Combine local cached scenes and newly fetched scenes
    total_scenes = fetched_scenes + [s for s in local_scenes if getattr(s, "provider_product_id", None) not in [getattr(fs, "provider_product_id", None) for fs in fetched_scenes]]
    
    if not total_scenes:
        return _unavailable("scene_validation", "no_scene_found", date_range, candidate_count=len(selected_features))
        
    return total_scenes
