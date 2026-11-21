"""IR-05: real-catalog completeness / temporal exactness adversarial gates.

These tests use fake HTTP responses rather than claiming to contact CDSE.
A live provider acceptance test remains required before scientific qualification.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from services.agribrain.layer0.archive.stac_client import STACClient
from services.agribrain.layer0.archive.archive_query import ArchiveQueryManager
from services.agribrain.layer0.archive.archive_fetcher import ArchiveFetcher


class _Auth:
    def get_auth_header(self):
        return {"Authorization": "Bearer test-placeholder"}


class _Response:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def _client(monkeypatch):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_OFFLINE", "false")
    monkeypatch.setenv("AGRIWISE_STAC_URL", "https://catalog.test/stac/search")
    return STACClient(cdse_client=_Auth())


def _search(client, *, limit=10, max_pages=10):
    return client.search(
        geometry_geojson={"type": "Point", "coordinates": [3, 36]},
        start_time="2026-06-16T12:45:00Z",
        end_time="2026-07-01T00:00:00Z",
        collections=["sentinel-2-l2a"], limit=limit, max_pages=max_pages,
    )


def _item(scene_id, at):
    return {"id": scene_id, "properties": {
        "datetime": at, "processing:level": "L2A",
        "eo:cloud_cover": 1.0,
    }, "assets": {}}


def test_ir05_stac_follows_get_continuation_and_collects_all_pages(monkeypatch):
    client = _client(monkeypatch)
    def post(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        return _Response({"features": [_item("A", "2026-06-20T00:00:00Z")],
                          "links": [{"rel": "next", "href": "?page=2", "method": "GET"}]})
    def get(url, **kwargs):
        assert url == "https://catalog.test/stac/search?page=2"
        return _Response({"features": [_item("B", "2026-06-21T00:00:00Z")],
                          "links": [], "numberMatched": 2})
    monkeypatch.setattr("services.agribrain.layer0.archive.stac_client.requests.post", post)
    monkeypatch.setattr("services.agribrain.layer0.archive.stac_client.requests.get", get)
    assert [x["id"] for x in _search(client)] == ["A", "B"]


def test_ir05_stac_follows_post_body_merged_next(monkeypatch):
    client = _client(monkeypatch)
    calls = []
    def post(url, **kwargs):
        data = kwargs["json"]
        calls.append(dict(data))
        if "token" not in data:
            return _Response({"features": [_item("A", "2026-06-20T00:00:00Z")],
                              "links": [{"rel": "next", "href": "/stac/search",
                                         "method": "POST", "body": {"token": "cursor2"},
                                         "merge": True}]})
        assert data["datetime"] == "2026-06-16T12:45:00Z/2026-07-01T00:00:00Z"
        assert data["token"] == "cursor2"
        return _Response({"features": [_item("B", "2026-06-21T00:00:00Z")],
                          "links": [], "numberMatched": 2})
    monkeypatch.setattr("services.agribrain.layer0.archive.stac_client.requests.post", post)
    assert [x["id"] for x in _search(client)] == ["A", "B"]
    assert len(calls) == 2


def test_ir05_stac_rejects_full_page_without_completion_proof(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.stac_client.requests.post",
        lambda *args, **kwargs: _Response({
            "features": [_item("A", "2026-06-20T00:00:00Z")], "links": [],
        }),
    )
    with pytest.raises(RuntimeError, match="stac_full_page_without_completion_proof"):
        _search(client, limit=1)


def test_ir05_stac_rejects_missing_page_despite_number_matched(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.stac_client.requests.post",
        lambda *args, **kwargs: _Response({
            "features": [_item("A", "2026-06-20T00:00:00Z")],
            "links": [], "numberMatched": 2,
        }),
    )
    with pytest.raises(RuntimeError, match="stac_missing_continuation_link"):
        _search(client)


def test_ir05_stac_refuses_cross_origin_next_with_auth_header(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.stac_client.requests.post",
        lambda *args, **kwargs: _Response({
            "features": [], "links": [
                {"rel": "next", "href": "https://other.test/steal", "method": "GET"},
            ],
        }),
    )
    with pytest.raises(RuntimeError, match="untrusted_stac_pagination_origin"):
        _search(client)


def test_ir05_stac_detects_circular_pagination(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.stac_client.requests.post",
        lambda *args, **kwargs: _Response({
            "features": [], "links": [
                {"rel": "next", "href": "/stac/search", "method": "POST"},
            ],
        }),
    )
    with pytest.raises(RuntimeError, match="stac_pagination_cycle_detected"):
        _search(client)


def test_ir05_stac_rejects_page_limit_before_completion(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        "services.agribrain.layer0.archive.stac_client.requests.post",
        lambda *args, **kwargs: _Response({
            "features": [], "links": [
                {"rel": "next", "href": "/stac/search?page=2", "method": "GET"},
            ],
        }),
    )
    with pytest.raises(RuntimeError, match="stac_pagination_limit_exhausted"):
        _search(client, max_pages=1)


def test_ir05_offline_stac_cannot_claim_empty_completed_window(monkeypatch):
    client = _client(monkeypatch)
    client.offline = True
    with pytest.raises(RuntimeError, match="stac_catalog_offline_not_complete"):
        _search(client)


def test_ir05_exact_utc_month_partition_does_not_expand_calendar_days():
    manager = ArchiveQueryManager(stac_client=object())
    windows = manager.partition_date_range(
        "2026-06-16T12:45:00Z", "2026-07-02T18:11:00Z",
    )
    assert windows == [
        ("2026-06-16T12:45:00Z", "2026-07-01T00:00:00Z"),
        ("2026-07-01T00:00:00Z", "2026-07-02T18:11:00Z"),
    ]


def test_ir05_query_excludes_inclusive_end_boundary_until_next_partition():
    class _Catalog:
        def __init__(self):
            self.calls = []
        def search(self, *, geometry_geojson, start_time, end_time, collections):
            self.calls.append((start_time, end_time))
            if start_time.startswith("2026-06-16"):
                return [
                    _item("S2_EARLY", "2026-06-16T12:45:00Z"),
                    _item("S2_BOUNDARY", "2026-07-01T00:00:00Z"),
                ]
            return [
                _item("S2_BOUNDARY", "2026-07-01T00:00:00Z"),
                _item("S2_LATE", "2026-07-02T18:11:00Z"),
            ]
    cat = _Catalog()
    manager = ArchiveQueryManager(stac_client=cat)
    selected = manager.execute_partitioned_query(
        geometry_geojson={"type": "Point", "coordinates": [3, 36]},
        start_date="2026-06-16T12:45:00Z", end_date="2026-07-02T18:11:00Z",
        sources=["sentinel2"],
    )
    assert [s.scene_id for s in selected] == ["S2_EARLY", "S2_BOUNDARY"]
    assert cat.calls == [
        ("2026-06-16T12:45:00Z", "2026-07-01T00:00:00Z"),
        ("2026-07-01T00:00:00Z", "2026-07-02T18:11:00Z"),
    ]


def test_ir05_query_rejects_malformed_catalog_scene_instead_of_skipping():
    class _Catalog:
        def search(self, **kwargs):
            return [{"id": "S2_BAD", "properties": {}, "assets": {}}]
    manager = ArchiveQueryManager(stac_client=_Catalog())
    with pytest.raises(RuntimeError, match="stac_scene_metadata_invalid"):
        manager.execute_partitioned_query(
            geometry_geojson={"type": "Point", "coordinates": [3, 36]},
            start_date="2026-06-16T12:45:00Z", end_date="2026-06-30T00:00:00Z",
            sources=["sentinel2"],
        )


def test_ir05_fetcher_rejects_quota_blockage_as_incomplete(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_OFFLINE", "false")
    fetcher = ArchiveFetcher(cache_dir=str(tmp_path), stac_client=_Auth())
    monkeypatch.setattr(
        fetcher.query_manager, "execute_partitioned_query",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        fetcher.download_planner, "plan_download",
        lambda **kwargs: (False, "quota_exhausted", []),
    )
    with patch(
        "services.agribrain.layer0.archive.archive_fetcher.calculate_aoi_footprint",
        return_value={"type": "Point", "coordinates": [3, 36]},
    ):
        with pytest.raises(RuntimeError, match="archive_download_plan_incomplete:quota_exhausted"):
            fetcher.orchestrate_fetch(
                plot_id="plot", geometry_wkt="POINT(3 36)",
                start_date="2026-06-16T12:45:00Z",
                end_date="2026-06-30T00:00:00Z",
                sources=["sentinel2"], manifest_only=True,
            )



def test_ir05_fetcher_rejects_successful_but_truncated_quota_plan(monkeypatch, tmp_path):
    """ArchiveDownloadPlanner can report success even after silently dropping scenes."""
    from types import SimpleNamespace
    monkeypatch.setenv("AGRIWISE_ARCHIVE_OFFLINE", "false")
    fetcher = ArchiveFetcher(cache_dir=str(tmp_path), stac_client=_Auth())
    catalog_scenes = [
        SimpleNamespace(source="sentinel2", scene_id="S2_A"),
        SimpleNamespace(source="sentinel2", scene_id="S2_B"),
    ]
    monkeypatch.setattr(
        fetcher.query_manager, "execute_partitioned_query",
        lambda **kwargs: catalog_scenes,
    )
    monkeypatch.setattr(
        fetcher.download_planner, "plan_download",
        lambda **kwargs: (True, "Success", catalog_scenes[:1]),
    )
    with patch(
        "services.agribrain.layer0.archive.archive_fetcher.calculate_aoi_footprint",
        return_value={"type": "Point", "coordinates": [3, 36]},
    ):
        with pytest.raises(RuntimeError, match="archive_download_plan_partial:discovered=2:planned=1"):
            fetcher.orchestrate_fetch(
                plot_id="plot", geometry_wkt="POINT(3 36)",
                start_date="2026-06-16T12:45:00Z",
                end_date="2026-06-30T00:00:00Z",
                sources=["sentinel2"], manifest_only=True,
            )



def test_ir05_missing_product_processing_level_is_not_fabricated():
    class _Catalog:
        def search(self, **kwargs):
            return [{"id": "S2_LEVEL_UNVERIFIED", "properties": {
                "datetime": "2026-06-20T00:00:00Z",
            }, "assets": {}}]
    manager = ArchiveQueryManager(stac_client=_Catalog())
    with pytest.raises(RuntimeError, match="stac_scene_metadata_invalid"):
        manager.execute_partitioned_query(
            geometry_geojson={"type": "Point", "coordinates": [3, 36]},
            start_date="2026-06-16T12:45:00Z",
            end_date="2026-06-30T00:00:00Z",
            sources=["sentinel2"],
        )
