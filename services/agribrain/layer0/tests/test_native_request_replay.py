"""B2B-02B exact provider PreparedRequest retention and replay protections.

Fixtures emulate the trusted internal requests.post response boundary. They
are NOT provider authentication, signed authority, or a production WORM test.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
import hashlib
import json

import pytest

from services.agribrain.layer0.native_issuer.acquisition_evidence import (
    NativeEvidenceError, NativeEvidenceStore, REQUEST_REPLAY_DOMAIN,
)

ENDPOINT = "https://sh.dataspace.copernicus.eu/process/v1"
REQUEST = {
    "input": {
        "bounds": {"bbox":[0.,0.,1.,1.]},
        "data": [{"type":"sentinel-2-l2a", "timeRange":{
            "from":"2026-11-02T11:55:00Z",
            "to":"2026-11-02T12:05:00Z",
        }}],
    },
    "output": {"width":2, "height":2},
    "evalscript": "//VERSION=3\nfunction evaluatePixel(s){return [s.B04];}",
}
TIME=datetime(2026,11,3,12,tzinfo=timezone.utc)


def _response(*, raw_request=None, request=REQUEST, raw_response=b"provider-raw-bytes"):
    raw_request = (
        json.dumps(request,indent=2).encode("utf-8")
        if raw_request is None else raw_request
    )
    return SimpleNamespace(
        url=ENDPOINT,status_code=200,content=raw_response,
        headers={"x-request-id":"fixture-provider-123"},
        request=SimpleNamespace(
            method="POST",url=ENDPOINT,
            headers={"Authorization":"Bearer fixture-server-only-token"},
            body=raw_request,
        ),
    )


def _capture(store, *, response=None, request=REQUEST):
    return store.capture_http_response(
        response=_response(request=request) if response is None else response,
        endpoint=ENDPOINT, request_parameters=request, sensor="S2",
        provider_product_id="S2-SELECTED-FIXTURE",
        credential_reference="backend_sentinel_oauth",
        retrieved_at=TIME,
    )


def _sidecar(store, receipt):
    path=store._path("request_replays",receipt.acquisition_id)
    return path,json.loads(path.read_bytes())


def test_original_prepared_post_bytes_are_retained_exactly(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    wire=json.dumps(REQUEST,indent=2).encode()
    receipt=_capture(store,response=_response(raw_request=wire))
    path,record=_sidecar(store,receipt)
    assert record["domain"] == REQUEST_REPLAY_DOMAIN
    assert record["acquisition_id"] == receipt.acquisition_id
    assert record["request_sha256"] == receipt.request_sha256
    assert record["wire_request_sha256"] == hashlib.sha256(wire).hexdigest()
    assert record["request_bytes"] == len(wire)
    assert store._path("request_wire",record["wire_request_sha256"]).read_bytes() == wire
    assert store.verified_request_body(receipt.acquisition_id) == REQUEST
    assert receipt.origin_class.value == "LIVE_PROVIDER_AUTHENTICATED"


def test_cold_reopen_replays_original_request_without_auth_headers(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    receipt=_capture(store)
    reopened=NativeEvidenceStore(tmp_path)
    body=reopened.verified_request_body(receipt.acquisition_id)
    assert body == REQUEST
    replay_path,replay=_sidecar(reopened,receipt)
    material=(replay_path.read_bytes()+
              reopened._path("request_wire",replay["wire_request_sha256"]).read_bytes())
    assert b"Bearer " not in material
    assert b"fixture-server-only-token" not in material


def test_legacy_capture_with_no_request_sidecar_does_not_reconstruct_from_hash(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    receipt=_capture(store)
    store._path("request_replays",receipt.acquisition_id).unlink()
    assert store.verified_cache_receipt(receipt.acquisition_id).acquisition_id == receipt.acquisition_id
    with pytest.raises(NativeEvidenceError,match="captured_request_not_retained"):
        store.verified_request_body(receipt.acquisition_id)


def test_mutated_original_wire_is_detected_even_if_response_manifest_is_valid(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    receipt=_capture(store)
    _,replay=_sidecar(store,receipt)
    store._path("request_wire",replay["wire_request_sha256"]).write_bytes(b'{"forged":true}')
    with pytest.raises(NativeEvidenceError,match="invalid_captured_request_evidence"):
        store.verified_request_body(receipt.acquisition_id)
    assert store.verified_cache_receipt(receipt.acquisition_id).acquisition_id == receipt.acquisition_id


@pytest.mark.parametrize("key,value",[
    ("request_sha256","a"*64),
    ("wire_request_sha256","a"*64),
    ("request_bytes",999999),
    ("acquisition_id","b"*64),
    ("domain","attacker-controlled"),
])
def test_modified_replay_metadata_rejects(tmp_path,key,value):
    store=NativeEvidenceStore(tmp_path)
    receipt=_capture(store)
    path,record=_sidecar(store,receipt)
    record[key]=value
    path.write_text(json.dumps(record),encoding="utf-8")
    with pytest.raises(NativeEvidenceError,match="invalid_captured_request_evidence"):
        store.verified_request_body(receipt.acquisition_id)


def test_duplicate_json_record_keys_reject_instead_of_last_one_wins(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    receipt=_capture(store)
    path,_record=_sidecar(store,receipt)
    content=path.read_text()
    path.write_text(content.replace('"domain":','"domain":"forged","domain":',1))
    with pytest.raises(NativeEvidenceError,match="invalid_captured_request_evidence"):
        store.verified_request_body(receipt.acquisition_id)


def test_missing_wire_bytes_or_missing_record_rejects(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    receipt=_capture(store)
    path,record=_sidecar(store,receipt)
    store._path("request_wire",record["wire_request_sha256"]).unlink()
    with pytest.raises(NativeEvidenceError,match="invalid_captured_request_evidence"):
        store.verified_request_body(receipt.acquisition_id)


def test_concurrent_idempotent_capture_is_replay_stable(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        captured=list(pool.map(lambda _: _capture(store),range(8)))
    assert len({r.acquisition_id for r in captured})==1
    assert store.verified_request_body(captured[0].acquisition_id)==REQUEST


def test_identical_canonical_json_with_changed_prepared_wire_cannot_replace_prior_wire(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    receipt=_capture(store)
    alternate=json.dumps(REQUEST,separators=(",",":")).encode()
    with pytest.raises(NativeEvidenceError,match="different content"):
        _capture(store,response=_response(raw_request=alternate))
    assert store.verified_request_body(receipt.acquisition_id)==REQUEST


def test_failed_replay_storage_cannot_expose_new_response_manifest(tmp_path,monkeypatch):
    store=NativeEvidenceStore(tmp_path)
    original=store._write_once
    def inject_io_failure(path,content):
        if path.parent.parent.name=="request_replays":
            raise OSError("fixture simulated storage failure")
        return original(path,content)
    monkeypatch.setattr(store,"_write_once",inject_io_failure)
    with pytest.raises(OSError,match="storage failure"):
        _capture(store)
    assert not list((tmp_path/"manifests").rglob("*")) if (tmp_path/"manifests").exists() else True


def test_wire_body_cannot_disagree_with_canonical_request_claim(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    wrong=dict(REQUEST)
    wrong["output"]={"width":99,"height":99}
    with pytest.raises(NativeEvidenceError,match="prepared provider request"):
        _capture(store,response=_response(request=wrong))


def test_invalid_missing_prepared_body_does_not_write_replay(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    bad=_response()
    bad.request.body=None
    with pytest.raises(NativeEvidenceError,match="prepared provider request"):
        _capture(store,response=bad)
    assert not (tmp_path/"request_replays").exists()


@pytest.mark.parametrize("secret", [
    "Bearer abcdef123456789", "Basic YWRtaW46cGFzcw==",
    "access_token=super_sensitive", "client_secret:super_sensitive",
    "api_key=super_sensitive",
])
def test_embedded_credential_values_never_persist(tmp_path,secret):
    store=NativeEvidenceStore(tmp_path)
    payload={**REQUEST,"evalscript": "//VERSION=3\\n// "+secret}
    with pytest.raises(NativeEvidenceError,match="credential"):
        _capture(store,request=payload)
    assert not (tmp_path/"request_wire").exists()
    assert not (tmp_path/"manifests").exists()


def test_replay_rejects_noncanonical_or_nonfinite_transmitted_json(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    wire=b'{"input":{"data":[]}, "bad": NaN}'
    with pytest.raises(NativeEvidenceError):
        _capture(store,response=_response(raw_request=wire))


def test_request_replay_cannot_read_a_second_acquisition_sidecar(tmp_path):
    store=NativeEvidenceStore(tmp_path)
    first=_capture(store)
    different={**REQUEST, "output":{"width":3,"height":2}}
    second=_capture(store,request=different)
    first_path,_=_sidecar(store,first)
    second_path,_=_sidecar(store,second)
    first_path.write_bytes(second_path.read_bytes())
    with pytest.raises(NativeEvidenceError,match="invalid_captured_request_evidence"):
        store.verified_request_body(first.acquisition_id)
