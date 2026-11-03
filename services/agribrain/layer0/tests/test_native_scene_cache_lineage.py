"""R18-RUNTIME-01: cold S1/S2 scenes retain only verified capture lineage.

No Sentinel Hub network calls, provider science qualification, grant signing,
or pilot publication authority are exercised by these cache fixtures.
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import pytest

from services.agribrain.layer0.archive.raster_store import RasterStore
from services.agribrain.layer0.native_issuer.acquisition_evidence import (
    NativeEvidenceStore, NativeEvidenceError, restore_cached_native_references,
)
from services.agribrain.layer0.asmae_scene_products import (
    s1_real_scene_product_fetcher as s1,
    s2_real_scene_product_fetcher as s2,
)

CATALOG = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
PROCESS = "https://sh.dataspace.copernicus.eu/process/v1"
WHEN = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
REQUEST = {"input": {"data": [{"type": "sentinel-2-l2a"}]}}


def _response(url, body):
    return SimpleNamespace(
        url=url, content=body, status_code=200,
        headers={"x-request-id": "fixture-provider-request-id"},
        request=SimpleNamespace(
            url=url, method="POST",
            headers={"Authorization": "Bearer fixture-not-secret-token"},
            body=json.dumps(REQUEST).encode(),
        ),
    )


def _capture_pair(root, sensor, product):
    store = NativeEvidenceStore(root)
    kwargs = {"request_parameters": REQUEST, "sensor": sensor,
              "credential_reference": "fixture_backend_credential",
              "retrieved_at": WHEN}
    catalog = store.capture_http_response(
        response=_response(CATALOG, b"catalog-native-response-" + sensor.encode()),
        endpoint=CATALOG, **kwargs,
    )
    process = store.capture_http_response(
        response=_response(PROCESS, b"process-native-response-" + product.encode()),
        endpoint=PROCESS, provider_product_id=product, **kwargs,
    )
    return catalog, process, store


def _metadata(sensor, product, catalog=None, process=None):
    meta = {
        "sensor": sensor, "scene_id": sensor.lower() + "_real_scene_1_test",
        "provider_product_id": product, "catalog_item_id": product,
        "acquisition_datetime": "2026-11-02T12:00:00+00:00",
        "crs": "EPSG:4326", "transform": [0.0, 0.01, 0.0, 1.0, 0.0, -0.01],
        "width": 2, "height": 2, "source_reality": "real_raster",
        "product_binding": "legacy_unproven",
        "quality": {"valid_fraction": 0.9},
        "relative_orbit": 12, "orbit_direction": "ASCENDING",
    }
    if catalog is not None and process is not None:
        meta.update({
            "native_catalog_acquisition_id": catalog.acquisition_id,
            "native_process_acquisition_id": process.acquisition_id,
            "native_evidence_status": "CAPTURED_UNQUALIFIED",
            "process_request_hash": process.request_sha256,
            "provider_response_hash": process.response_sha256,
        })
    return meta


def _fetch_cold(monkeypatch, tmp_path, sensor, meta):
    module = s1 if sensor == "S1" else s2
    cache_root = tmp_path / "cache" / sensor
    scene_dir = cache_root / meta["provider_product_id"]
    scene_dir.mkdir(parents=True, exist_ok=True)
    (scene_dir / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    raster = RasterStore()
    bands = ("VV", "VH", "dataMask") if sensor == "S1" else ("B04", "B08", "SCL")
    for band in bands:
        raster.save_band(str(scene_dir / (band + ".npz")), np.ones((2, 2), dtype=np.float32))

    class FakeStore:
        base_dir = str(cache_root)
        raster_store = raster

    monkeypatch.setattr(module, "SceneProductStore", lambda *a, **kw: FakeStore())
    monkeypatch.setenv("ASMAE_TEST_OVERRIDE", "false")
    monkeypatch.delenv("SENTINEL_HUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SENTINEL_HUB_CLIENT_SECRET", raising=False)
    return (
        module.fetch_asmae_s1_scene_stack if sensor == "S1"
        else module.fetch_asmae_s2_scene_stack
    )(
        plot_id="unique-native-cache-test-plot", run_id="cache-run",
        date_range=("2026-11-01", "2026-11-03"),
        raster_composites={},
    )


@pytest.mark.parametrize("sensor", ["S1", "S2"])
def test_full_cold_fetch_preserves_verified_catalog_and_process_ids(monkeypatch, tmp_path, sensor):
    evidence_root = tmp_path / "evidence"
    product = sensor + "-EXACT-CACHE-ITEM"
    catalog, process, _store = _capture_pair(evidence_root, sensor, product)
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", str(evidence_root))
    loaded = _fetch_cold(monkeypatch, tmp_path, sensor,
                         _metadata(sensor, product, catalog, process))
    assert isinstance(loaded, list), loaded
    assert len(loaded) == 1
    scene = loaded[0]
    assert scene.native_catalog_acquisition_id == catalog.acquisition_id
    assert scene.native_process_acquisition_id == process.acquisition_id
    assert scene.native_evidence_status == "PROVENANCE_VERIFIED_CACHE"
    serialized = scene.to_dict()
    assert serialized["native_catalog_acquisition_id"] == catalog.acquisition_id
    assert serialized["native_process_acquisition_id"] == process.acquisition_id
    assert serialized["native_evidence_status"] == "PROVENANCE_VERIFIED_CACHE"
    assert scene.diagnostic_only is True  # no physical-science qualification


@pytest.mark.parametrize("sensor", ["S1", "S2"])
def test_tampered_native_object_blocks_cold_scene(monkeypatch, tmp_path, sensor):
    evidence_root = tmp_path / "evidence"
    product = sensor + "-EXACT-CACHE-ITEM"
    catalog, process, store = _capture_pair(evidence_root, sensor, product)
    store._path("objects", process.object_id).write_bytes(b"tampered")
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", str(evidence_root))
    result = _fetch_cold(monkeypatch, tmp_path, sensor,
                         _metadata(sensor, product, catalog, process))
    assert isinstance(result, dict)
    assert result["status"] == "unavailable"
    assert result["reason"] == "invalid_native_cache_evidence"


@pytest.mark.parametrize("sensor", ["S1", "S2"])
def test_legacy_unattested_cache_retains_no_synthetic_provenance(monkeypatch, tmp_path, sensor):
    monkeypatch.delenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", raising=False)
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "true")
    result = _fetch_cold(monkeypatch, tmp_path, sensor,
                         _metadata(sensor, sensor + "-LEGACY-ITEM"))
    assert isinstance(result, list), result
    assert result[0].native_evidence_status == "UNATTESTED"
    assert result[0].native_catalog_acquisition_id is None
    assert "native_process_acquisition_id" not in result[0].to_dict()


def test_wrong_sensor_or_provider_product_cannot_reuse_valid_capture(tmp_path, monkeypatch):
    catalog, process, _ = _capture_pair(tmp_path, "S2", "S2-REAL")
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", str(tmp_path))
    with pytest.raises(NativeEvidenceError):
        restore_cached_native_references(
            _metadata("S1", "S2-REAL", catalog, process), sensor="S1"
        )
    with pytest.raises(NativeEvidenceError):
        restore_cached_native_references(
            _metadata("S2", "S2-OTHER", catalog, process), sensor="S2"
        )


def test_missing_root_cannot_claim_verified_cache_origin(monkeypatch, tmp_path):
    catalog, process, _ = _capture_pair(tmp_path, "S2", "S2-REAL")
    meta = _metadata("S2", "S2-REAL", catalog, process)
    monkeypatch.delenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", raising=False)
    monkeypatch.delenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", raising=False)
    assert restore_cached_native_references(meta, sensor="S2") == (
        None, None, "UNATTESTED",
    )
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "true")
    with pytest.raises(NativeEvidenceError):
        restore_cached_native_references(meta, sensor="S2")


def test_partial_native_cache_references_fail_closed():
    with pytest.raises(NativeEvidenceError, match="incomplete"):
        restore_cached_native_references(
            {"native_catalog_acquisition_id": "a" * 64}, sensor="S2",
        )
