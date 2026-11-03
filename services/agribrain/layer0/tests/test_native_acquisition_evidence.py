"""B2B-01 native acquisition traces — not cryptographic provider attestation.

Test-only fabricated HTTP response objects cannot mint a Kalman grant.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib
import json

import pytest

from services.agribrain.layer0.native_issuer.acquisition_evidence import (
    EVIDENCE_DOMAIN, MAX_RESPONSE_BYTES, NativeAcquisitionReceipt,
    NativeEvidenceError, NativeEvidenceStore, OriginClass,
    capture_backend_provider_response,
)
from services.agribrain.layer0.asmae_scene_products.scene_product_schema import SceneProduct


ENDPOINT = "https://sh.dataspace.copernicus.eu/process/v1"
CATALOG = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
TIME = datetime(2026, 11, 3, 12, 30, tzinfo=timezone.utc)
REQUEST = {
    "input": {"data": [{"type": "sentinel-2-l2a"}]},
    "output": {"width": 2, "height": 2},
}


def response(body=b"raw-sentinel-raster-bytes", *, url=ENDPOINT, status=200,
             authorization="Bearer test-only-nonsecret-token",
             sent_parameters=None):
    return SimpleNamespace(
        content=body, url=url, status_code=status,
        headers={"x-request-id": "req-123", "Content-Type": "application/tar"},
        request=SimpleNamespace(
            method="POST", url=url, headers={"Authorization": authorization},
            body=json.dumps(REQUEST if sent_parameters is None else sent_parameters).encode(),
        ),
    )


def capture(store, **kw):
    request_parameters = kw.pop("request_parameters", REQUEST)
    return store.capture_http_response(
        response=kw.pop("response", response(sent_parameters=request_parameters)),
        endpoint=kw.pop("endpoint", ENDPOINT),
        request_parameters=request_parameters,
        sensor=kw.pop("sensor", "S2"),
        provider_product_id=kw.pop("provider_product_id", "S2-EXACT-ID"),
        credential_reference=kw.pop("credential_reference", "backend_oauth_reference"),
        retrieved_at=kw.pop("retrieved_at", TIME),
        **kw,
    )


def test_native_capture_persists_exact_bytes_and_request_hash(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    receipt = capture(store)
    assert isinstance(receipt, NativeAcquisitionReceipt)
    assert receipt.origin_class is OriginClass.LIVE_PROVIDER_AUTHENTICATED
    assert receipt.qualification_status == "NOT_QUALIFIED"
    assert receipt.provider_signature_verified is False
    assert receipt.response_sha256 == hashlib.sha256(response().content).hexdigest()
    assert receipt.object_id == receipt.response_sha256
    assert store._path("objects", receipt.object_id).read_bytes() == response().content
    manifest = json.loads(store._path("manifests", receipt.acquisition_id).read_bytes())
    assert manifest["domain"] == EVIDENCE_DOMAIN
    assert manifest["acquisition_id"] == receipt.acquisition_id
    assert "Authorization" not in json.dumps(manifest)
    assert "test-only-nonsecret-token" not in json.dumps(manifest)


def test_cache_reverification_never_promotes_a_local_record_to_live(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    original = capture(store)
    cached = store.verified_cache_receipt(original.acquisition_id)
    assert cached.origin_class is OriginClass.PROVENANCE_VERIFIED_CACHE
    assert cached.acquisition_id == original.acquisition_id
    assert cached.provider_signature_verified is False
    assert cached.qualification_status == "NOT_QUALIFIED"


def test_same_capture_is_content_addressable_and_idempotent(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    one = capture(store)
    two = capture(store)
    assert one.acquisition_id == two.acquisition_id
    assert len(list((tmp_path / "objects").rglob(one.response_sha256))) == 1


def test_request_bytes_product_and_retrieval_time_bind_acquisition_id(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    first = capture(store)
    changed_request = capture(store, request_parameters={
        "input": {"data": [{"type": "sentinel-1-grd"}]},
    })
    changed_time = capture(store, retrieved_at=datetime(2026, 11, 3, 12, 31, tzinfo=timezone.utc))
    changed_product = capture(store, provider_product_id="S2-DIFFERENT-ID")
    changed_raw = capture(store, response=response(body=b"different-bands"))
    assert len({first.acquisition_id, changed_request.acquisition_id,
                changed_time.acquisition_id, changed_product.acquisition_id,
                changed_raw.acquisition_id}) == 5


def test_tampered_raw_bytes_fail_closed_on_cache_lookup(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    item = capture(store)
    store._path("objects", item.object_id).write_bytes(b"attacker-overwrite")
    with pytest.raises(NativeEvidenceError, match="cached acquisition"):
        store.verified_cache_receipt(item.acquisition_id)
    with pytest.raises(NativeEvidenceError, match="different content"):
        capture(store)


def test_tampered_manifest_or_claimed_origin_cannot_gain_authority(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    item = capture(store)
    path = store._path("manifests", item.acquisition_id)
    payload = json.loads(path.read_bytes())
    payload["qualification_status"] = "QUALIFIED"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(NativeEvidenceError, match="cached acquisition"):
        store.verified_cache_receipt(item.acquisition_id)


def test_request_with_secret_field_is_rejected_without_storing(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    with pytest.raises(NativeEvidenceError, match="forbidden"):
        capture(store, request_parameters={"input": {"api_key": "stolen"}})
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize("bad_endpoint", [
    "http://sh.dataspace.copernicus.eu/process/v1",
    "https://evil.invalid/process/v1",
    "https://sh.dataspace.copernicus.eu/process/v1?token=bad",
])
def test_only_allowlisted_exact_https_endpoints_are_accepted(tmp_path, bad_endpoint):
    with pytest.raises(NativeEvidenceError, match="endpoint"):
        capture(NativeEvidenceStore(tmp_path), endpoint=bad_endpoint)


def test_wrong_response_url_status_and_missing_service_authorization_are_denied(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    for r in (
        response(url=CATALOG),
        response(status=403),
        response(authorization=""),
    ):
        with pytest.raises(NativeEvidenceError):
            capture(store, response=r)


@pytest.mark.parametrize("invalid", [
    {"temperature": float("nan")},
    {"data": object()},
    {"client-secret": "oops"},
])
def test_noncanonical_or_secret_request_is_denied(tmp_path, invalid):
    with pytest.raises(NativeEvidenceError):
        capture(NativeEvidenceStore(tmp_path), request_parameters=invalid)


def test_naive_retrieval_time_is_rejected(tmp_path):
    with pytest.raises(NativeEvidenceError, match="aware"):
        capture(NativeEvidenceStore(tmp_path), retrieved_at=datetime(2026, 11, 3))


def test_empty_or_oversized_response_fails_closed(tmp_path, monkeypatch):
    import services.agribrain.layer0.native_issuer.acquisition_evidence as evidence
    store = NativeEvidenceStore(tmp_path)
    with pytest.raises(NativeEvidenceError):
        capture(store, response=response(body=b""))
    assert MAX_RESPONSE_BYTES == 256 * 1024 * 1024
    # Exercise the very same size guard without allocating a 256 MiB fixture.
    monkeypatch.setattr(evidence, "MAX_RESPONSE_BYTES", 4)
    with pytest.raises(NativeEvidenceError, match="oversized"):
        capture(store, response=response(body=b"012345"))


def test_backend_adapter_absent_root_is_unattested_not_live(monkeypatch):
    monkeypatch.delenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", raising=False)
    monkeypatch.delenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", raising=False)
    assert capture_backend_provider_response(
        response=response(), endpoint=ENDPOINT, request_parameters=REQUEST,
        sensor="S2",
    ) is None


def test_backend_adapter_strict_mode_requires_store(monkeypatch):
    monkeypatch.delenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", raising=False)
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "true")
    with pytest.raises(NativeEvidenceError, match="trusted root"):
        capture_backend_provider_response(
            response=response(), endpoint=ENDPOINT, request_parameters=REQUEST,
            sensor="S2",
        )


def test_backend_adapter_capture_also_remains_scientifically_unqualified(tmp_path, monkeypatch):
    monkeypatch.setenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", str(tmp_path))
    monkeypatch.setenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "true")
    item = capture_backend_provider_response(
        response=response(), endpoint=ENDPOINT, request_parameters=REQUEST,
        sensor="S2", provider_product_id="exact-selected-scene",
    )
    assert item is not None
    assert item.qualification_status == "NOT_QUALIFIED"
    assert item.provider_signature_verified is False


def test_same_capture_from_multiple_workers_does_not_truncate_existing_object(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as workers:
        items = list(workers.map(lambda _: capture(store), range(8)))
    assert len({x.acquisition_id for x in items}) == 1
    assert store.verified_cache_receipt(items[0].acquisition_id).response_bytes == len(response().content)


def test_scene_product_fields_remain_evidence_links_not_state_authority():
    item = SceneProduct(
        scene_id="s2", sensor="S2", acquisition_datetime=TIME,
        crs="EPSG:4326", transform=(0, 1, 0, 0, 0, -1),
        width=2, height=2,
        native_catalog_acquisition_id="a" * 64,
        native_process_acquisition_id="b" * 64,
        native_evidence_status="CAPTURED_UNQUALIFIED",
    )
    output = item.to_dict()
    assert output["native_process_acquisition_id"] == "b" * 64
    assert output["native_evidence_status"] == "CAPTURED_UNQUALIFIED"
    assert output["real_provider_product"] is False
    assert output["diagnostic_only"] is True


def test_caller_cannot_claim_different_request_than_prepared_wire_post(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    false_claim = {"input": {"data": [{"type": "sentinel-1-grd"}]}}
    with pytest.raises(NativeEvidenceError, match="prepared provider request"):
        capture(store, response=response(sent_parameters=REQUEST),
                request_parameters=false_claim)
    assert not list((tmp_path / "manifests").rglob("*")) if (tmp_path / "manifests").exists() else True


def test_prepared_http_method_and_url_must_match_original_endpoint(tmp_path):
    store = NativeEvidenceStore(tmp_path)
    bad = response()
    bad.request.method = "GET"
    with pytest.raises(NativeEvidenceError, match="expected backend POST"):
        capture(store, response=bad)
    bad = response()
    bad.request.url = CATALOG
    with pytest.raises(NativeEvidenceError, match="expected backend POST"):
        capture(store, response=bad)
