import os
import json
import asyncio
import pytest
import numpy as np
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.common.surface_hashing import (
    compute_raster_bytes_hash,
    SURFACE_HASH_CONTRACT_VERSION,
)
from services.agribrain.app.internal_service_auth import (
    rfc3986_encode,
    canonicalize_query_params,
    compute_request_signature,
    require_internal_service_request,
)
from services.agribrain.orchestrator_v2.schema import OrchestratorInput
from services.agribrain.layer10_sire.schema import Layer10Input
from fastapi import HTTPException, Request


def test_plot_namespace_zero_fallback():
    ns = PlotNamespace(tenant_id="t1", farm_id="f1", plot_id="p1")
    assert ns.is_valid()
    assert str(ns) == "t1:f1:p1"

    invalid_ns = PlotNamespace(tenant_id="", farm_id="f1", plot_id="p1")
    assert not invalid_ns.is_valid()


def test_shared_hmac_test_vectors():
    vectors_path = os.path.join(
        os.path.dirname(__file__),
        "../../../packages/contracts/internal_auth_test_vectors.json",
    )
    with open(vectors_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    secret = data["secret"]
    for vec in data["vectors"]:
        qp = [(pair[0], pair[1]) for pair in vec["query_params"]]
        canon_qp = canonicalize_query_params(qp)
        assert canon_qp == vec.get("expected_canonical_query", canon_qp)

        sig = compute_request_signature(
            secret=secret,
            method=vec["method"],
            path=vec["pathname"],
            query_string=qp,
            tenant_id=vec["tenant_id"],
            farm_id=vec["farm_id"],
            plot_id=vec["plot_id"],
            timestamp=vec["timestamp"],
            nonce=vec["nonce"],
            key_version=vec.get("key_version", "v1"),
            body_bytes=vec["body_text"].encode("utf-8"),
        )
        assert sig == vec["expected_signature"]


def test_2d_surface_hashing():
    grid_2d = [[0.1, 0.2], [0.3, float("nan")]]
    h1 = compute_raster_bytes_hash(grid_2d)
    assert len(h1) == 64
    assert SURFACE_HASH_CONTRACT_VERSION == "r5_hash_v3_surface_identity"

    arr_2d = np.array([[0.1, 0.2], [0.3, np.nan]])
    h2 = compute_raster_bytes_hash(arr_2d)
    assert h1 == h2


def test_orchestrator_input_kw_only_namespace():
    ns = PlotNamespace(tenant_id="t", farm_id="f", plot_id="p")
    inp = OrchestratorInput(plot_namespace=ns)
    assert inp.plot_id == "p"
    assert inp.tenant_id == "t"
    assert inp.farm_id == "f"


def test_layer10_input_kw_only_namespace():
    ns = PlotNamespace(tenant_id="t", farm_id="f", plot_id="p")
    l10 = Layer10Input(plot_namespace=ns)
    assert l10.plot_id == "p"
    assert l10.tenant_id == "t"
    assert l10.farm_id == "f"


def test_internal_auth_path_plot_id_equality():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v2/progress/p1",
        "headers": [
            (b"x-agribrain-signature", b"bad-sig"),
            (b"x-agribrain-timestamp", b"100"),
            (b"x-agribrain-nonce", b"n1"),
            (b"x-tenant-id", b"t1"),
            (b"x-farm-id", b"f1"),
            (b"x-plot-id", b"p1"),
        ],
    }
    req = Request(scope)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_internal_service_request(req))
    assert exc_info.value.status_code == 401
