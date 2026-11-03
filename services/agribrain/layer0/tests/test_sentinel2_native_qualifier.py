"""B2B-02 Sentinel-2 independently replayed native QA acceptance cases.

Synthetic captured responses are test-only backend-request stand-ins. A pass
means bounded optical *screening*, not independent provider trust, plot IAM,
grant issuance or publication authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import json
import tarfile

import numpy as np
import pytest
import tifffile

from services.agribrain.layer0.archive.raster_store import RasterStore
from services.agribrain.layer0.asmae_scene_products.product_binding import (
    verify_exact_product_binding,
)
from services.agribrain.layer0.asmae_scene_products.s2_real_scene_product_fetcher import (
    _stable_array_hash,
)
from services.agribrain.layer0.asmae_scene_products.scene_product_schema import SceneProduct
from services.agribrain.layer0.native_issuer.acquisition_evidence import NativeEvidenceStore
from services.agribrain.layer0.native_issuer.sentinel2_qualifier import (
    S2ScreenStatus, TrustedPlotContext, screen_sentinel2_native,
)

CATALOG = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
PROCESS = "https://sh.dataspace.copernicus.eu/process/v1"
ITEM = "S2A_MSIL2A_20261102T120000_N0100_R101_T31SAA_20261102T140000"
ACQUISITION = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
RETRIEVAL = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
POLYGON = TrustedPlotContext(
    plot_id="plot-from-backend-registry", geometry_hash="geometry-hash-pinned",
    geometry_version=7,
    polygon_wgs84=((0.,0.),(1.,0.),(1.,1.),(0.,1.)),
)
CATALOG_REQUEST = {"collections":["sentinel-2-l2a"], "bbox":[0,0,1,1]}
PROCESS_REQUEST = {
    "input": {
        "bounds": {
            "bbox": [0.,0.,1.,1.],
            "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
        },
        "data": [{
            "type": "sentinel-2-l2a",
            "dataFilter": {"mosaickingOrder": "leastCC"},
            "timeRange": {
                "from": "2026-11-02T11:55:00Z",
                "to": "2026-11-02T12:05:00Z",
            },
        }],
    },
    "output": {
        "width":4, "height":4,
        "responses": [
            {"identifier": name, "format": {"type":"image/tiff"}}
            for name in ("B04","B08","SCL","dataMask")
        ] + [{"identifier": "userdata", "format": {"type":"application/json"}}],
    },
    "evalscript": '//VERSION=3\nconst EXPECTED_PRODUCT_ID = ' + json.dumps(ITEM) + ';',
}


def _resp(endpoint, request, body):
    return SimpleNamespace(
        url=endpoint, status_code=200, content=body,
        headers={"x-request-id":"test-provider-response"},
        request=SimpleNamespace(
            method="POST", url=endpoint,
            headers={"Authorization": "Bearer fixture-credential-reference"},
            body=json.dumps(request).encode("utf-8"),
        ),
    )


def _tar_bytes(bands, userdata):
    destination=BytesIO()
    with tarfile.open(mode="w",fileobj=destination) as tar:
        for name, array in bands.items():
            f=BytesIO()
            tifffile.imwrite(f,np.asarray(array))
            body=f.getvalue()
            member=tarfile.TarInfo(name=name + ".tif")
            member.size=len(body)
            tar.addfile(member,BytesIO(body))
        body=json.dumps(userdata).encode("utf-8")
        member=tarfile.TarInfo("userdata.json")
        member.size=len(body)
        tar.addfile(member,BytesIO(body))
    return destination.getvalue()


def _native_scene(
    tmp_path, *, scl_value=4, dm_value=1, returned_product=ITEM,
    catalog_item=ITEM, collection="sentinel-2-l2a",
    catalog_features=None, b04_value=0.2, b08_value=0.6,
    remove_band=None, process_request=None,
):
    store=NativeEvidenceStore(tmp_path/"evidence")
    rstore=RasterStore()
    bands={
        "B04":np.full((4,4),b04_value,dtype=np.float32),
        "B08":np.full((4,4),b08_value,dtype=np.float32),
        "SCL":np.full((4,4),scl_value,dtype=np.uint8),
        "DATAMASK":np.full((4,4),dm_value,dtype=np.uint8),
    }
    if remove_band:
        del bands[remove_band]
    userdata={"userData": {"tiles": [{"sentinel2ProductId":returned_product}]}}
    if catalog_features is None:
        catalog_features=[{
            "id":catalog_item,"collection":collection,
            "properties":{"datetime":"2026-11-02T12:00:00Z","eo:cloud_cover":5.0},
        }]
    cat_bytes=json.dumps({"features":catalog_features}).encode()
    process_bytes=_tar_bytes(bands,userdata)
    cr=store.capture_http_response(
        response=_resp(CATALOG,CATALOG_REQUEST,cat_bytes),
        endpoint=CATALOG,request_parameters=CATALOG_REQUEST,sensor="S2",
        credential_reference="test-backend-provider",retrieved_at=RETRIEVAL,
    )
    native_process_request = PROCESS_REQUEST if process_request is None else process_request
    pr=store.capture_http_response(
        response=_resp(PROCESS,native_process_request,process_bytes),
        endpoint=PROCESS,request_parameters=native_process_request,
        sensor="S2",provider_product_id=ITEM,
        credential_reference="test-backend-provider",retrieved_at=RETRIEVAL,
    )
    refs={}
    for name, array in bands.items():
        path=tmp_path/"bands"/(name+".npz")
        rstore.save_band(str(path),array)
        refs[name]=str(path)
    binding=verify_exact_product_binding(ITEM,userdata,"S2")
    scene=SceneProduct(
        scene_id="native-s2-qualifier-fixture",sensor="S2",
        acquisition_datetime=ACQUISITION,
        crs="EPSG:4326",transform=(0.,0.25,0.,1.,0.,-0.25),
        width=4,height=4,band_refs=refs,
        mask_refs={name:refs[name] for name in ("SCL","DATAMASK") if name in refs},
        band_units={"B04":"reflectance","B08":"reflectance",
                    "SCL":"classification","DATAMASK":"binary_mask"},
        quality={"valid_fraction":1.0},
        source_reality="real_raster",test_override=False,
        production_usable=False,diagnostic_only=True,
        provider_product_id=ITEM,catalog_item_id=ITEM,
        content_hash=_stable_array_hash(bands),
        process_request_hash=pr.request_sha256,
        provider_response_hash=pr.response_sha256,
        native_catalog_acquisition_id=cr.acquisition_id,
        native_process_acquisition_id=pr.acquisition_id,
        native_evidence_status="CAPTURED_UNQUALIFIED",
        product_binding="exact_catalog_item",
        binding_proof=binding["proof"],
    )
    return scene,store,cr,pr,refs


def _screen(scene, store, *, trusted_plot=POLYGON):
    return screen_sentinel2_native(
        scene=scene,evidence_store=store,trusted_plot=trusted_plot,
    )


def test_true_captured_s2_bands_pass_bounded_qa_without_admission_authority(tmp_path):
    scene,store,*_= _native_scene(tmp_path)
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.SCREENED_NATIVE_QA
    assert result.proof_hash and len(result.proof_hash)==64
    assert result.diagnostic_metrics["valid_fraction"]==1.0
    assert result.diagnostic_metrics["valid_pixel_centers"]==16
    assert 0.49 < result.diagnostic_metrics["ndvi_mean"] < 0.51
    assert result.eligible_for_state_grant is False
    assert result.scientific_publication_authorized is False
    assert scene.production_usable is False and scene.diagnostic_only is True


def test_bounded_proof_is_deterministic_for_replay(tmp_path):
    scene,store,*_= _native_scene(tmp_path)
    assert _screen(scene,store).proof_hash == _screen(scene,store).proof_hash


def test_missing_trusted_plot_defers_native_qa_not_authorized(tmp_path):
    scene,store,*_= _native_scene(tmp_path)
    result=_screen(scene,store,trusted_plot=None)
    assert result.status is S2ScreenStatus.DEFERRED_SPATIAL_AUTHORITY
    assert result.proof_hash is None


def test_missing_original_process_request_defers_legacy_capture(tmp_path):
    scene,store,_catalog,process,_refs=_native_scene(tmp_path)
    store._path("request_replays",process.acquisition_id).unlink()
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.DEFERRED_SPATIAL_AUTHORITY
    assert result.reason == "historical_native_capture_missing_original_request"


def test_tampered_captured_wire_request_fails_closed(tmp_path):
    scene,store,_catalog,process,_refs=_native_scene(tmp_path)
    record=json.loads(store._path("request_replays",process.acquisition_id).read_bytes())
    store._path("request_wire",record["wire_request_sha256"]).write_bytes(b'{"forged":true}')
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.REJECTED
    assert result.reason == "invalid_captured_process_request_evidence"


def test_wrong_catalog_selected_product_rejects(tmp_path):
    scene,store,*_= _native_scene(tmp_path,catalog_item="OTHER_S2_PRODUCT")
    assert _screen(scene,store).reason == "missing_or_ambiguous_catalog_product"


def test_ambiguous_duplicate_catalog_features_rejects(tmp_path):
    item={"id":ITEM,"collection":"sentinel-2-l2a",
          "properties":{"datetime":"2026-11-02T12:00:00Z"}}
    scene,store,*_= _native_scene(tmp_path,catalog_features=[item,item])
    assert _screen(scene,store).reason == "missing_or_ambiguous_catalog_product"


def test_wrong_catalog_collection_rejects(tmp_path):
    scene,store,*_= _native_scene(tmp_path,collection="sentinel-1-grd")
    assert _screen(scene,store).reason == "wrong_catalog_collection"


def test_wrong_process_tile_product_rejects(tmp_path):
    scene,store,*_= _native_scene(tmp_path,returned_product="WRONG_PRODUCT_ID")
    assert _screen(scene,store).reason == "catalog_process_product_mismatch"


@pytest.mark.parametrize("band",["B04","B08","SCL","DATAMASK"])
def test_required_raw_band_absent_rejects(tmp_path,band):
    scene,store,*_= _native_scene(tmp_path,remove_band=band)
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.REJECTED


@pytest.mark.parametrize("scl,dm",[(9,1),(4,0),(0,1),(11,1)])
def test_cloud_shadow_snow_nodata_or_zero_mask_rejects(tmp_path,scl,dm):
    scene,store,*_= _native_scene(tmp_path,scl_value=scl,dm_value=dm)
    assert _screen(scene,store).reason=="insufficient_masked_plot_pixel_quality"


def test_bare_soil_validity_is_not_falsely_zero_quality(tmp_path):
    scene,store,*_= _native_scene(tmp_path,scl_value=5,b04_value=0.3,b08_value=0.3)
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.SCREENED_NATIVE_QA
    assert abs(result.diagnostic_metrics["ndvi_mean"])<1e-9


@pytest.mark.parametrize("bad_reflectance",[-0.01,1.5,float("nan")])
def test_out_of_range_or_nonfinite_optical_band_rejects(tmp_path,bad_reflectance):
    scene,store,*_= _native_scene(tmp_path,b04_value=bad_reflectance)
    assert _screen(scene,store).reason=="insufficient_masked_plot_pixel_quality"


def test_altered_cached_raster_pixel_rejects(tmp_path):
    scene,store,_,_,refs=_native_scene(tmp_path)
    RasterStore().save_band(refs["B08"],np.full((4,4),0.1,dtype=np.float32))
    assert _screen(scene,store).reason=="cached_raster_differs_from_captured_process"


def test_missing_native_catalog_raw_object_rejects(tmp_path):
    scene,store,cr,*_=_native_scene(tmp_path)
    store._path("objects",cr.object_id).unlink()
    assert _screen(scene,store).status is S2ScreenStatus.REJECTED


def test_altered_scene_product_binding_proof_rejects(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    scene.binding_proof["process_userdata_hash"]="0"*64
    assert _screen(scene,store).reason=="unmatched_original_process_binding_proof"


def test_scene_geometry_grid_fabrication_rejects(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    scene.transform=(0.,0.3,0.,1.,0.,-0.25)
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.DEFERRED_SPATIAL_AUTHORITY


def test_foreign_plot_footprint_outside_scene_rejects(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    scope=TrustedPlotContext(
        plot_id="wrong",geometry_hash="geo",geometry_version=2,
        polygon_wgs84=((1.5,1.5),(1.7,1.5),(1.7,1.7),(1.5,1.7)),
    )
    assert _screen(scene,store,trusted_plot=scope).reason=="plot_outside_native_raster_extent"


def test_incomplete_native_evidence_links_reject(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    scene.native_process_acquisition_id=None
    assert _screen(scene,store).reason=="missing_native_scene_evidence"


def test_test_override_cannot_be_screened_as_native(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    scene.test_override=True
    assert _screen(scene,store).reason=="missing_native_scene_evidence"


def test_zero_red_and_zero_nir_is_undefined_ndvi_not_genuine_zero(tmp_path):
    scene,store,*_=_native_scene(tmp_path,b04_value=0.0,b08_value=0.0)
    assert _screen(scene,store).reason == "insufficient_masked_plot_pixel_quality"


def test_unsigned_claims_and_production_usable_flags_cannot_bypass_qa(tmp_path):
    scene,store,*_=_native_scene(tmp_path,scl_value=9)
    scene.production_usable = True
    scene.real_provider_product = True
    scene.diagnostic_only = False
    scene.usable_for_advisory = True
    assert _screen(scene,store).status is S2ScreenStatus.REJECTED


def test_wrong_optical_band_units_reject_even_when_pixels_are_valid(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    scene.band_units["B08"]="derived_feature"
    assert _screen(scene,store).reason == "unqualified_reflectance_units"


@pytest.mark.parametrize("bad", [0, -1, 1, "0.7", float("nan"), 1.2, 0.2])
def test_unvalidated_qa_policy_rejected(tmp_path,bad):
    scene,store,*_=_native_scene(tmp_path)
    assert _screen(scene,store).status is S2ScreenStatus.SCREENED_NATIVE_QA
    result=screen_sentinel2_native(
        scene=scene,evidence_store=store,trusted_plot=POLYGON,
        min_valid_fraction=bad,
    )
    assert result.status is S2ScreenStatus.REJECTED


def test_scene_acquisition_in_the_future_relative_to_capture_denies(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    scene.acquisition_datetime=datetime(2026,11,4,12,tzinfo=timezone.utc)
    assert _screen(scene,store).status is S2ScreenStatus.REJECTED


def test_accepted_screen_does_not_claim_calibrated_sigma_or_mesia(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.SCREENED_NATIVE_QA
    assert result.diagnostic_metrics["screened_variables"] == ["ndvi"]
    assert result.diagnostic_metrics["sigma_calibrated"] is False
    assert result.diagnostic_metrics["support_method"] == "EPSG4326_PIXEL_CENTER_SAMPLE_ONLY"
    assert result.eligible_for_state_grant is False


def test_complex_plot_boundary_defers_to_mesia_instead_of_implicit_truncation(tmp_path):
    import math
    scene,store,*_=_native_scene(tmp_path)
    ring=tuple(
        (.5+.3*math.cos(i*2*math.pi/270),
         .5+.3*math.sin(i*2*math.pi/270))
        for i in range(270)
    )
    scope=TrustedPlotContext(
        plot_id="plot-from-backend-registry", geometry_hash="fine-boundary-hash",
        geometry_version=9, polygon_wgs84=ring,
    )
    result=_screen(scene,store,trusted_plot=scope)
    assert result.status is S2ScreenStatus.DEFERRED_SPATIAL_AUTHORITY
    assert result.reason=="robust_mesia_geometry_support_required"


def test_cold_reopened_evidence_store_independently_replays_post_request(tmp_path):
    scene,store,_catalog,process,_refs=_native_scene(tmp_path)
    reopened=NativeEvidenceStore(store.root)
    assert reopened.verified_request_body(process.acquisition_id) == PROCESS_REQUEST
    result=_screen(scene,reopened)
    assert result.status is S2ScreenStatus.SCREENED_NATIVE_QA


def test_wire_replay_record_sha_or_receipt_swap_rejects(tmp_path):
    scene,store,_catalog,process,_refs=_native_scene(tmp_path)
    path=store._path("request_replays",process.acquisition_id)
    record=json.loads(path.read_bytes())
    record["request_sha256"]="0"*64
    path.write_text(json.dumps(record))
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.REJECTED
    assert result.reason == "invalid_captured_process_request_evidence"


def test_missing_replay_wire_object_rejects_instead_of_synthesizing_request(tmp_path):
    scene,store,_catalog,process,_refs=_native_scene(tmp_path)
    record=json.loads(store._path("request_replays",process.acquisition_id).read_bytes())
    store._path("request_wire",record["wire_request_sha256"]).unlink()
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.REJECTED
    assert result.reason == "invalid_captured_process_request_evidence"


def test_native_qa_has_no_caller_supplied_request_override(tmp_path):
    scene,store,*_=_native_scene(tmp_path)
    import inspect
    parameters=inspect.signature(screen_sentinel2_native).parameters
    assert "captured_process_request" not in parameters
    assert _screen(scene,store).status is S2ScreenStatus.SCREENED_NATIVE_QA


@pytest.mark.parametrize("mutation", ["bbox", "time_window", "product"])
def test_original_post_request_is_independently_rejected_when_wrong(tmp_path,mutation):
    changed=json.loads(json.dumps(PROCESS_REQUEST))
    if mutation == "bbox":
        changed["input"]["bounds"]["bbox"]=[0,0,2,2]
    elif mutation == "time_window":
        changed["input"]["data"][0]["timeRange"]={
            "from":"2026-11-01T00:00:00Z",
            "to":"2026-11-01T01:00:00Z",
        }
    else:
        changed["evalscript"]='//VERSION=3\\nconst EXPECTED_PRODUCT_ID = "WRONG_ITEM";'
    scene,store,*_=_native_scene(tmp_path,process_request=changed)
    result=_screen(scene,store)
    assert result.status is S2ScreenStatus.REJECTED
    assert result.reason == "captured_process_request_grid_or_time_mismatch"
