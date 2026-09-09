import asyncio
from copy import deepcopy

import pytest
from fastapi import HTTPException, Request

from services.agribrain.app.crop_label_authority import (
    assess_crop_dataset_release_readiness,
    derive_farmer_crop_label_authority,
)
from services.agribrain.app.internal_service_auth import (
    require_internal_service_request,
)
from services.agribrain.common.plot_namespace import PlotNamespace


def test_browser_crop_label_authority_is_server_derived_and_unverified():
    authority = derive_farmer_crop_label_authority(
        PlotNamespace(tenant_id="user-7", farm_id="farm-2", plot_id="plot-3")
    )

    assert authority == {
        "label_source": "farmer_confirmed",
        "label_confidence": "LOW",
        "created_by": "user-7",
        "verification_status": "unverified",
        "training_eligible": False,
    }


def test_dataset_volume_never_self_authorizes_production_release():
    readiness = assess_crop_dataset_release_readiness(500)

    assert readiness["dataset_training_ready"] is True
    assert readiness["production_model_eligible"] is False
    assert readiness["production_release_validation"] == {
        "required": True,
        "status": "not_completed",
    }


def test_unsigned_crop_label_request_is_rejected():
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/v2/crop-label",
        "query_string": b"",
        "headers": [],
    })

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_internal_service_request(request))

    assert exc_info.value.status_code == 401


def test_crop_label_body_plot_mismatch_preserves_forbidden_status():
    from services.agribrain.app.main import (
        CropLabelRequest,
        api_v2_crop_label,
    )

    request = CropLabelRequest(plot_id="plot-body", crop_code="tomato")
    namespace = PlotNamespace(
        tenant_id="user-7", farm_id="farm-2", plot_id="plot-header"
    )

    with pytest.raises(HTTPException) as exc_info:
        api_v2_crop_label(request, namespace=namespace)

    assert exc_info.value.status_code == 403


def test_crop_identify_body_plot_mismatch_preserves_forbidden_status():
    from services.agribrain.app.main import (
        CropIdentifyRequest,
        api_v2_crop_identify,
    )

    request = CropIdentifyRequest(
        plot_id="plot-body", lat=36.7, lng=3.1
    )
    namespace = PlotNamespace(
        tenant_id="user-7", farm_id="farm-2", plot_id="plot-header"
    )

    with pytest.raises(HTTPException) as exc_info:
        api_v2_crop_identify(request, namespace=namespace)

    assert exc_info.value.status_code == 403


class _RuntimeCollection:
    def __init__(self, rows=()):
        self.rows = list(deepcopy(rows))

    def find_one(self, query, sort=None):
        rows = []
        for row in self.rows:
            matches = True
            for key, expected in query.items():
                actual = row.get(key)
                if isinstance(expected, dict) and "$ne" in expected:
                    matches = matches and actual != expected["$ne"]
                elif isinstance(expected, dict) and "$nin" in expected:
                    matches = matches and actual not in expected["$nin"]
                elif isinstance(expected, dict) and "$in" in expected:
                    matches = matches and actual in expected["$in"]
                else:
                    matches = matches and actual == expected
            if matches:
                rows.append(row)
        if sort:
            for key, direction in reversed(sort):
                rows.sort(key=lambda item: item.get(key), reverse=direction < 0)
        return deepcopy(rows[0]) if rows else None

    def insert_one(self, document):
        self.rows.append(deepcopy(document))

    def update_one(self, query, update):
        for row in self.rows:
            if all(row.get(key) == value for key, value in query.items()):
                row.update(deepcopy(update.get("$set") or {}))
                return


class _RuntimeDatabase:
    def __init__(self):
        self.collections = {
            "Plot": _RuntimeCollection([
                {"_id": "plot-runtime", "farmId": "farm-runtime"},
            ]),
            "Farm": _RuntimeCollection([
                {"_id": "farm-runtime", "userId": "tenant-runtime"},
            ]),
            "CropCycle": _RuntimeCollection(),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_crop_label_endpoint_returns_canonical_runtime_receipt_when_audit_fails(
    monkeypatch,
):
    from layer2_veg_int.labels import label_store
    from services.agribrain.app.main import (
        CropLabelRequest,
        api_v2_crop_label,
    )

    database = _RuntimeDatabase()

    class _Client:
        closed = False

        def close(self):
            self.closed = True

    class _Store:
        instances = []

        def __init__(self, _uri):
            self.db = database
            self.client = _Client()
            self.instances.append(self)

        def save_label(self, _label):
            raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(label_store, "MongoLabelStore", _Store)
    monkeypatch.setenv("MONGODB_URI", "mongodb://unused/agriwise")
    namespace = PlotNamespace(
        tenant_id="tenant-runtime",
        farm_id="farm-runtime",
        plot_id="plot-runtime",
    )

    result = api_v2_crop_label(
        CropLabelRequest(plot_id="plot-runtime", crop_code="tomato"),
        namespace=namespace,
    )

    assert result["runtime_declaration"]["crop_code"] == "tomato"
    assert result["runtime_declaration"]["authority"] == "FARMER_CONFIRMED"
    assert result["runtime_declaration"]["plant_date_asserted"] is False
    assert result["audit_record"] == {
        "status": "failed",
        "role": "unverified_training_candidate_only",
        "label_id": None,
    }
    assert "crop_label_audit_record_not_persisted" in result[
        "quality"
    ]["warnings"]
    assert _Store.instances[0].client.closed is True
