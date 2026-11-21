"""IR-05: complete 2015+ scene inventory vs bounded trusted raster acquisition.

These tests use controlled catalog records and HTTP response objects.
They never claim to have downloaded real Sentinel scenes or assimilated states.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.agribrain.layer0.archive.archive_fetcher import ArchiveFetcher


class _Auth:
    def get_auth_header(self):
        return {"Authorization": "Bearer deliberately-test-only-token"}


class _STAC:
    stac_url = "https://api.dataspace.copernicus.eu/stac/search"

    def __init__(self):
        self.cdse_client = _Auth()


def _fetcher(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_OFFLINE", "false")
    monkeypatch.delenv("AGRIWISE_ARCHIVE_MANIFEST_ONLY", raising=False)
    return ArchiveFetcher(cache_dir=str(tmp_path), stac_client=_STAC())


def _scene(scene_id, date="2026-09-01T10:00:00Z"):
    return SimpleNamespace(
        scene_id=scene_id, source="sentinel2", acquisition_time=date,
        product_level="L2A", tile_id="T31SDA", cloud_score=4.0,
        asset_urls={}, remote_hash=hashlib.sha256(scene_id.encode()).hexdigest(),
        metadata={
            "valid_pixel_fraction": 0.95,
            "proj:epsg": 32631,
            "proj:transform": [10, 0, 500000, 0, -10, 4060000],
            "gsd": 10,
            "collection": "sentinel-2-l2a",
        },
    )


def test_ir05_manifest_inventory_not_limited_to_500_raster_scene_quota(monkeypatch, tmp_path):
    fetcher = _fetcher(monkeypatch, tmp_path)
    scenes = [_scene(f"S2A_{i:04d}") for i in range(505)]
    monkeypatch.setattr(fetcher.query_manager, "execute_partitioned_query", lambda **_: scenes)
    def forbidden_plan(**kwargs):
        raise AssertionError("raster quota planner must never truncate pure catalog inventory")
    monkeypatch.setattr(fetcher.download_planner, "plan_download", forbidden_plan)
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.archive_fetcher.calculate_aoi_footprint",
        lambda _: {"type": "Polygon", "coordinates": []},
    )
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.archive_fetcher.check_tile_overlap",
        lambda *args: 1.0,
    )
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.archive_fetcher.compute_scene_quality_score",
        lambda **kwargs: 0.96,
    )
    published = []
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.archive_fetcher.save_scene_manifest",
        lambda **kwargs: published.extend(kwargs["records"]),
    )
    result = fetcher.orchestrate_fetch(
        plot_id="plot-a", geometry_wkt="POLYGON((3 36, 4 36, 4 37, 3 36))",
        start_date="2026-09-01T00:00:00Z", end_date="2026-09-30T00:00:00Z",
        sources=["sentinel2"], manifest_only=True,
    )
    assert len(result) == 505
    assert len(published) == 505
    assert len({r.scene_id for r in result}) == 505
    assert all(not r.local_cache_refs for r in result)


def test_ir05_asset_untrusted_stac_href_never_receives_cdse_token(monkeypatch, tmp_path):
    fetcher = _fetcher(monkeypatch, tmp_path)
    def should_not_call(*args, **kwargs):
        raise AssertionError("unsafe origin reached network")
    import requests
    monkeypatch.setattr(requests, "get", should_not_call)
    with pytest.raises(RuntimeError, match="archive_asset_download_not_verified"):
        fetcher._download_real_assets(
            SimpleNamespace(asset_urls={"B04": "https://untrusted.example/data.tif"}),
            ["B04"], str(tmp_path / "safe"), {},
        )
    assert not list(tmp_path.rglob("*.tif"))


def test_ir05_asset_requires_all_requested_bands(monkeypatch, tmp_path):
    fetcher = _fetcher(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="archive_required_asset_missing"):
        fetcher._download_real_assets(
            SimpleNamespace(asset_urls={}), ["B04"], str(tmp_path / "safe"), {},
        )


def test_ir05_cdn_fetch_uses_no_bearer_and_commits_atomically(monkeypatch, tmp_path):
    fetcher = _fetcher(monkeypatch, tmp_path)
    monkeypatch.setenv("AGRIWISE_ARCHIVE_ALLOWED_ASSET_HOSTS", "safe-cdn.example")
    calls = []
    class Response:
        status_code = 200
        headers = {"Content-Length": "6"}
        def raise_for_status(self): pass
        def iter_content(self, chunk_size): return iter((b"abc", b"def"))
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    import requests
    monkeypatch.setattr(requests, "get", get)
    refs = {}
    fetcher._download_real_assets(
        SimpleNamespace(asset_urls={"B04": "https://safe-cdn.example/asset.tif"}),
        ["B04"], str(tmp_path / "safe"), refs,
    )
    assert Path(refs["B04"]).read_bytes() == b"abcdef"
    assert calls[0][1]["headers"] == {}
    assert calls[0][1]["allow_redirects"] is False
    assert not list((tmp_path / "safe").glob("*.partial"))


def test_ir05_cdse_same_origin_may_receive_scoped_token(monkeypatch, tmp_path):
    fetcher = _fetcher(monkeypatch, tmp_path)
    calls = []
    class Response:
        status_code = 200
        headers = {}
        def raise_for_status(self): pass
        def iter_content(self, chunk_size): return iter((b"raster",))
    import requests
    monkeypatch.setattr(
        requests, "get", lambda url, **kwargs:
        (calls.append(kwargs) or Response()),
    )
    refs = {}
    fetcher._download_real_assets(
        SimpleNamespace(asset_urls={
            "B04": "https://api.dataspace.copernicus.eu/stac/assets/b04.tif"
        }), ["B04"], str(tmp_path / "safe"), refs,
    )
    assert calls[0]["headers"]["Authorization"].startswith("Bearer ")
    assert Path(refs["B04"]).exists()


def test_ir05_redirect_and_truncated_asset_fail_without_partial_file(monkeypatch, tmp_path):
    fetcher = _fetcher(monkeypatch, tmp_path)
    import requests
    class Redirect:
        status_code = 302
        headers = {"Location": "https://evil.example"}
        def raise_for_status(self): pass
    monkeypatch.setattr(requests, "get", lambda *a, **k: Redirect())
    with pytest.raises(RuntimeError, match="archive_asset_download_not_verified"):
        fetcher._download_real_assets(
            SimpleNamespace(asset_urls={
                "B04": "https://api.dataspace.copernicus.eu/stac/assets/b04.tif"
            }), ["B04"], str(tmp_path / "safe"), {},
        )
    class TooLarge:
        status_code = 200
        headers = {}
        def raise_for_status(self): pass
        def iter_content(self, chunk_size): return iter((b"aa", b"bbbbbbbb"))
    monkeypatch.setattr(requests, "get", lambda *a, **k: TooLarge())
    monkeypatch.setenv("AGRIWISE_ARCHIVE_MAX_ASSET_BYTES", "5")
    with pytest.raises(RuntimeError, match="archive_asset_download_not_verified"):
        fetcher._download_real_assets(
            SimpleNamespace(asset_urls={
                "B04": "https://api.dataspace.copernicus.eu/stac/assets/b04.tif"
            }), ["B04"], str(tmp_path / "safe"), {},
        )
    assert not list(tmp_path.rglob("*.partial"))
    assert not list(tmp_path.rglob("*.tif"))


def test_ir05_archive_path_component_safety_before_provider_query(monkeypatch, tmp_path):
    fetcher = _fetcher(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="archive_plot_id_path_component_invalid"):
        fetcher.orchestrate_fetch(
            plot_id="../../other-tenant",
            geometry_wkt="POLYGON((3 36, 4 36, 4 37, 3 36))",
            start_date="2026-09-01T00:00:00Z",
            end_date="2026-09-30T00:00:00Z",
            sources=["sentinel2"], manifest_only=True,
        )
